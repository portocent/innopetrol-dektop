"""LogCanvas: interactive widget that draws a whole well (headers + tracks).

Navigation:
  wheel             scroll in depth
  Ctrl/⌘ + wheel    zoom around the cursor (also trackpad pinch)
  Shift + wheel     scroll horizontally
  PgUp/PgDn, Home/End, arrows
  dragging a track's border changes its width; double-clicking a track edits it.
"""

from __future__ import annotations

import math
import time

import numpy as np
from PySide6.QtCore import QEvent, QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from innopetrol.i18n import _
from innopetrol.model.scales import next_preset, px_per_unit, scale_ratio
from innopetrol.render.painter import BORDER, DepthTransform, RenderOptions, header_height
from innopetrol.render.scene import paint_headers, paint_log, paint_tops_overlay, track_edges, total_width
from innopetrol.ui.document import WellDocument
from innopetrol.ui.tile_cache import TILE_H, TileCache

MIN_TRACK_W = 40
EDGE_GRAB = 4
# If drawing a full screen costs more than this, zoom/resize/drag show a cheap preview and the
# full-quality drawing happens once the gesture stops (slow machines).
FRAME_BUDGET_MS = 30
SETTLE_MS = 160


class LogCanvas(QWidget):
    viewChanged = Signal()
    trackActivated = Signal(int)
    contextRequested = Signal(int, float, object)  # track index (-1 = none), depth, global position
    selectionChanged = Signal(int)

    def __init__(self, doc: WellDocument, parent=None, show_top_labels: bool = True):
        super().__init__(parent)
        self.doc = doc
        self.show_top_labels = show_top_labels
        self.ppu = 1.0
        self.top = doc.view.start
        self.x_offset = 0.0
        self.fit_mode = True
        self.depth_shift = 0.0  # for correlation: added to the displayed depth
        self.selected = -1
        self._cursor_y: float | None = None
        self._drag: tuple[int, float, int] | None = None  # (track, start x, start width)
        self._header_h = 60.0
        self.min_header_h = 0.0  # in correlation every well uses the same header height
        self.clamp_enabled = True
        self._version = 0  # increases with every layout change: invalidates the cache
        self._tiles = TileCache()
        self._header_pm: QPixmap | None = None
        self._header_key = None
        self._prefetch = QTimer(self)
        self._prefetch.setSingleShot(True)
        self._prefetch.timeout.connect(self._prefetch_tiles)
        self._tile_ms = 0.0  # measured cost of drawing a tile (moving average)
        self._previewing = False
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.timeout.connect(self._end_preview)
        self._drag_pending: tuple[int, int] | None = None  # (track, width) while dragging in guide mode
        self.setAttribute(Qt.WA_OpaquePaintEvent)  # we paint the whole background: Qt need not clear it
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(200, 200)
        self.setAutoFillBackground(False)
        doc.layoutChanged.connect(self._layout_changed)
        doc.cursorMoved.connect(self._external_cursor)

    # ------------------------------------------------------------------ geometry and scale

    @property
    def well(self):
        """The well as drawn (display depth reference and unit); data stays in MD in doc.well."""
        return self.doc.view

    @property
    def header_h(self) -> float:
        return self._header_h

    @property
    def body_h(self) -> float:
        return max(self.height() - self._header_h, 10)

    def _update_header_h(self):
        fm = QFontMetricsF(self.font())
        computed = max((header_height(t, fm) for t in self.doc.layout.tracks), default=fm.height() * 3)
        self._header_h = max(computed, self.min_header_h)

    def natural_header_h(self) -> float:
        fm = QFontMetricsF(self.font())
        return max((header_height(t, fm) for t in self.doc.layout.tracks), default=fm.height() * 3)

    @property
    def dpi(self) -> float:
        return self.logicalDpiY() or 96

    def current_scale(self) -> float:
        return scale_ratio(self.ppu, self.dpi, self.well.depth_unit)

    def set_scale(self, ratio: float, anchor_depth: float | None = None) -> None:
        self.fit_mode = False
        self._set_ppu(px_per_unit(ratio, self.dpi, self.well.depth_unit), anchor_depth)

    def fit(self) -> None:
        self.fit_mode = True
        span = max(self.well.stop - self.well.start, 1e-6)
        self.ppu = self.body_h / span
        self.top = self.well.start + self.depth_shift
        self._changed()

    def zoom(self, factor: float, anchor_depth: float | None = None, interactive: bool = False) -> None:
        self.fit_mode = False
        if interactive:
            self._begin_preview()
        self._set_ppu(self.ppu * factor, anchor_depth)

    def zoom_step(self, direction: int) -> None:
        """Zoom in (+1) or out (-1) to the next standard scale, keeping the visible center."""
        self.set_scale(next_preset(self.current_scale(), direction))

    def _pinch(self, value: float, y: float) -> None:
        """Trackpad pinch: value is the relative change (0.1 = 10 % closer)."""
        anchor = self.depth_at(y) + self.depth_shift if y > self._header_h else None
        self.zoom(1 + value, anchor, interactive=True)

    def event(self, e):
        # macOS (and Wayland) deliver pinch as a native gesture; on Windows it arrives as Ctrl + wheel.
        if e.type() == QEvent.NativeGesture and e.gestureType() == Qt.ZoomNativeGesture:
            self._pinch(e.value(), e.position().y())
            return True
        return super().event(e)

    # ------------------------------------------------------------------ adaptive drawing

    def frame_cost_ms(self) -> float:
        """Estimated cost of drawing the whole view from scratch, as measured on this machine."""
        return self._tile_ms * (math.ceil(self.body_h / TILE_H) + 1)

    def _begin_preview(self):
        if self.frame_cost_ms() > FRAME_BUDGET_MS:
            self._previewing = True
            self._settle.start(SETTLE_MS)

    def _end_preview(self):
        self._previewing = False
        self.update()

    def _set_ppu(self, ppu: float, anchor_depth: float | None):
        min_ppu = self.body_h / max(self.well.stop - self.well.start, 1e-6) / 4
        ppu = min(max(ppu, min_ppu), 400.0)
        if anchor_depth is None:
            anchor_depth = self.top + self.body_h / 2 / self.ppu
        anchor_y = (anchor_depth - self.top) * self.ppu
        self.ppu = ppu
        self.top = anchor_depth - anchor_y / ppu
        self._clamp()
        self._changed()

    def scroll_range(self) -> tuple[float, float]:
        """Allowed range for the top visible depth."""
        pad = 20 / self.ppu
        lo = self.well.start - pad + self.depth_shift
        hi = max(lo, self.well.stop + pad - self.body_h / self.ppu + self.depth_shift)
        return lo, hi

    def set_view(self, top: float, ppu: float) -> None:
        """Sets the view without anchoring (used to keep several wells in sync)."""
        self.fit_mode = False
        self.top, self.ppu = top, ppu
        self._clamp()
        self.update()

    def set_top(self, top: float) -> None:
        self.top = top
        self._clamp()
        self._changed()

    def scroll_by_px(self, dy: float) -> None:
        self.set_top(self.top + dy / self.ppu)

    def center_on(self, depth: float) -> None:
        self.set_top(depth + self.depth_shift - self.body_h / 2 / self.ppu)

    def _clamp(self):
        if self.clamp_enabled:
            lo, hi = self.scroll_range()
            self.top = min(max(self.top, lo), hi)
        max_x = max(0.0, total_width(self.doc.layout) - self.width())
        self.x_offset = min(max(self.x_offset, 0.0), max_x)

    def _changed(self):
        self.update()
        self.viewChanged.emit()

    def invalidate(self):
        """Drops cached drawings (call when anything visible in the log changes)."""
        self._version += 1
        self.update()

    def _layout_changed(self):
        self._version += 1
        self._update_header_h()
        if self.selected >= len(self.doc.layout.tracks):
            self.selected = -1
        if self.fit_mode:
            self.fit()
        else:
            self._clamp()
            self._changed()

    def transform(self) -> DepthTransform:
        # depth_shift moves the well (flattening on a top during correlation)
        return DepthTransform(self.top - self.depth_shift, self.ppu)

    def depth_at(self, y: float) -> float:
        return self.transform().depth(y - self._header_h)

    def y_of(self, depth: float) -> float:
        return float(self.transform().y(depth)) + self._header_h

    def track_at(self, x: float) -> int:
        for i, (tx, w) in enumerate(track_edges(self.doc.layout)):
            if tx - self.x_offset <= x < tx + w - self.x_offset:
                return i
        return -1

    def _edge_at(self, x: float) -> int:
        """Index of the track whose right border is under x (for resizing)."""
        for i, (tx, w) in enumerate(track_edges(self.doc.layout)):
            if abs(tx + w - self.x_offset - x) <= EDGE_GRAB:
                return i
        return -1

    # ------------------------------------------------------------------ Qt events

    def showEvent(self, e):
        super().showEvent(e)
        self._layout_changed()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.fit_mode:
            self._begin_preview()
            self.fit()
        else:
            self._clamp()
            self.viewChanged.emit()

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(e.rect(), QColor("#d5d8dc"))
        p.setRenderHint(QPainter.TextAntialiasing)
        tf = self.transform()
        self._paint_header(p)
        self._paint_body(p, tf)
        opts = RenderOptions(top_labels=self.show_top_labels)
        paint_tops_overlay(p, self.doc.layout, self.well, tf, -self.x_offset, self._header_h, self.body_h, opts)
        if self._cursor_y is not None and self._cursor_y > self._header_h:
            self._paint_cursor(p, self._cursor_y)
        if self._drag_pending:
            self._paint_drag_guide(p)
        p.end()
        if not self._previewing:
            self._prefetch.start(0)

    def _dpr(self) -> float:
        return self.devicePixelRatioF() or 1.0

    def _paint_header(self, p: QPainter):
        width = total_width(self.doc.layout)
        if width <= 0:
            return
        dpr = self._dpr()
        key = (self._version, self.selected, self._header_h, dpr, self.font().key())
        if key != self._header_key or self._header_pm is None:
            pm = QPixmap(QSize(math.ceil(width * dpr), math.ceil(self._header_h * dpr)))
            pm.setDevicePixelRatio(dpr)
            pm.fill(QColor("#d5d8dc"))
            hp = QPainter(pm)
            hp.setFont(self.font())
            hp.setRenderHint(QPainter.TextAntialiasing)
            paint_headers(hp, self.doc.layout, self.well, 0, 0, self._header_h, RenderOptions(), self.selected)
            hp.end()
            self._header_pm, self._header_key = pm, key
        p.drawPixmap(QPointF(-self.x_offset, 0), self._header_pm)

    def _tile_range(self, tf: DepthTransform) -> tuple[int, int, float]:
        base = tf.top * self.ppu  # absolute y (in pixels) of the top of the body
        return math.floor(base / TILE_H), math.floor((base + self.body_h) / TILE_H), base

    def _paint_body(self, p: QPainter, tf: DepthTransform):
        width = total_width(self.doc.layout)
        if width <= 0:
            return
        key = (self._version, self.ppu, self._dpr(), self.font().key())
        old = self._tiles.key
        if self._previewing and old is not None and old != key and old[0] == key[0] and old[2:] == key[2:] \
                and len(self._tiles):
            self._paint_preview(p, tf, old_ppu=old[1])
            return
        self._tiles.validate(key)
        k0, k1, base = self._tile_range(tf)
        p.save()
        p.setClipRect(QRectF(0, self._header_h, self.width(), self.body_h))
        for k in range(k0, k1 + 1):
            pm = self._tile(k)
            p.drawPixmap(QPointF(-self.x_offset, round(self._header_h + k * TILE_H - base)), pm)
        p.restore()

    def _paint_preview(self, p: QPainter, tf: DepthTransform, old_ppu: float):
        """Preview during a gesture: tiles from the previous scale stretched to the new one."""
        p.save()
        p.setClipRect(QRectF(0, self._header_h, self.width(), self.body_h))
        ratio = self.ppu / old_ppu
        for k, pm in self._tiles.items():
            y = self._header_h + (k * TILE_H / old_ppu - tf.top) * self.ppu
            h = TILE_H * ratio
            if y + h < self._header_h or y > self.height():
                continue
            target = QRectF(-self.x_offset, y, pm.width() / pm.devicePixelRatio(), h)
            p.drawPixmap(target, pm, QRectF(0, 0, pm.width(), pm.height()))
        p.restore()

    def _paint_drag_guide(self, p: QPainter):
        i, width = self._drag_pending
        x = track_edges(self.doc.layout)[i][0] + width - self.x_offset
        p.setPen(QPen(QColor("#2e86c1"), 2, Qt.DashLine))
        p.drawLine(QPointF(x, 0), QPointF(x, self.height()))

    def _tile(self, k: int) -> QPixmap:
        pm = self._tiles.get(k)
        if pm is None:
            pm = self._render_tile(k)
            self._tiles.put(k, pm)
        return pm

    def _render_tile(self, k: int) -> QPixmap:
        dpr = self._dpr()
        width = total_width(self.doc.layout)
        pm = QPixmap(QSize(math.ceil(width * dpr), math.ceil(TILE_H * dpr)))
        pm.setDevicePixelRatio(dpr)
        pm.fill(QColor("#d5d8dc"))
        tp = QPainter(pm)
        tp.setFont(self.font())
        tp.setRenderHint(QPainter.TextAntialiasing)
        opts = RenderOptions(draw_tops=False, frame_ends=False, dpr=dpr)
        tf = DepthTransform(k * TILE_H / self.ppu, self.ppu)
        t0 = time.perf_counter()
        paint_log(tp, self.doc.layout, self.well, tf, 0, 0, 0, TILE_H, opts, draw_headers=False)
        tp.end()
        ms = (time.perf_counter() - t0) * 1000
        self._tile_ms = ms if self._tile_ms == 0 else 0.7 * self._tile_ms + 0.3 * ms
        return pm

    def _prefetch_tiles(self):
        """While the application is idle, pre-renders the tiles above and below the view."""
        if not self.isVisible() or total_width(self.doc.layout) <= 0:
            return
        k0, k1, _base = self._tile_range(self.transform())
        for k in (k1 + 1, k0 - 1):
            if k not in self._tiles:
                self._tiles.put(k, self._render_tile(k))
                self._prefetch.start(0)  # one at a time so the interface never blocks
                return

    def _paint_cursor(self, p: QPainter, y: float):
        w = min(total_width(self.doc.layout) - self.x_offset, self.width())
        p.setPen(QPen(QColor(231, 76, 60, 200), 1, Qt.SolidLine))
        p.drawLine(QPointF(0, y), QPointF(w, y))
        depth = self.depth_at(y)
        text = f"{depth:.2f} {self.well.depth_unit}"
        fm = QFontMetricsF(self.font())
        box = QRectF(4, y - fm.height() - 2, fm.horizontalAdvance(text) + 8, fm.height())
        p.fillRect(box, QColor(255, 255, 255, 230))
        p.setPen(BORDER)
        p.drawText(box, Qt.AlignCenter, text)

    def wheelEvent(self, e):
        delta = e.angleDelta()
        steps = delta.y() / 120 if delta.y() else 0
        if e.modifiers() & Qt.ControlModifier:
            anchor = self.depth_at(e.position().y()) if e.position().y() > self._header_h else None
            if anchor is not None:
                anchor += self.depth_shift
            self.zoom(1.2 ** steps, anchor, interactive=True)
        elif e.modifiers() & Qt.ShiftModifier or delta.x():
            dx = delta.x() if delta.x() else delta.y()
            self.x_offset -= dx / 2
            self._clamp()
            self._changed()
        else:
            pixel = e.pixelDelta().y()
            self.scroll_by_px(-pixel if pixel else -steps * 80)
        e.accept()

    def keyPressEvent(self, e):
        page = self.body_h * 0.9
        key = e.key()
        if key == Qt.Key_PageDown:
            self.scroll_by_px(page)
        elif key == Qt.Key_PageUp:
            self.scroll_by_px(-page)
        elif key == Qt.Key_Down:
            self.scroll_by_px(30)
        elif key == Qt.Key_Up:
            self.scroll_by_px(-30)
        elif key == Qt.Key_Home:
            self.set_top(self.scroll_range()[0])
        elif key == Qt.Key_End:
            self.set_top(self.scroll_range()[1])
        elif key in (Qt.Key_Plus, Qt.Key_Equal):
            self.zoom_step(1)
        elif key == Qt.Key_Minus:
            self.zoom_step(-1)
        else:
            super().keyPressEvent(e)

    def mousePressEvent(self, e):
        x = e.position().x()
        if e.button() == Qt.LeftButton:
            edge = self._edge_at(x)
            if edge >= 0:
                self._drag = (edge, x, self.doc.layout.tracks[edge].width)
                return
            idx = self.track_at(x)
            if idx != self.selected:
                self.selected = idx
                self.selectionChanged.emit(idx)
                self.update()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        x, y = e.position().x(), e.position().y()
        if self._drag:
            i, x0, w0 = self._drag
            width = int(max(MIN_TRACK_W, w0 + x - x0))
            if self.frame_cost_ms() > FRAME_BUDGET_MS:
                # Slow machine: show a guide line and apply the width on release.
                self._drag_pending = (i, width)
                self.update()
            else:
                self.doc.layout.tracks[i].width = width
                self.invalidate()
            return
        self.setCursor(Qt.SplitHCursor if self._edge_at(x) >= 0 else Qt.ArrowCursor)
        if y > self._header_h and self.track_at(x) >= 0:
            self._set_cursor_y(y)
            self.doc.cursorMoved.emit(float(self.well.to_md(self.depth_at(y))))
        else:
            self._set_cursor_y(None)
            self.doc.cursorMoved.emit(math.nan)

    def _cursor_rect(self, y: float | None) -> QRect | None:
        if y is None:
            return None
        fm_h = QFontMetricsF(self.font()).height()
        return QRect(0, int(y - fm_h - 4), self.width(), int(fm_h + 8))

    def _set_cursor_y(self, y: float | None):
        """Moves the cursor line repainting only the affected strips, not the whole widget."""
        if y == self._cursor_y:
            return
        for rect in (self._cursor_rect(self._cursor_y), self._cursor_rect(y)):
            if rect is not None:
                self.update(rect)
        self._cursor_y = y

    def mouseReleaseEvent(self, e):
        if self._drag:
            self._drag = None
            if self._drag_pending:
                i, width = self._drag_pending
                self._drag_pending = None
                self.doc.layout.tracks[i].width = width
            self.doc.layoutChanged.emit()
            return
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        idx = self.track_at(e.position().x())
        if idx >= 0 and self._edge_at(e.position().x()) < 0:
            self.trackActivated.emit(idx)

    def leaveEvent(self, e):
        self._set_cursor_y(None)
        self.doc.cursorMoved.emit(math.nan)
        super().leaveEvent(e)

    def contextMenuEvent(self, e):
        idx = self.track_at(e.pos().x())
        if idx != self.selected:
            self.selected = idx
            self.selectionChanged.emit(idx)
            self.update()
        depth = self.depth_at(e.pos().y()) if e.pos().y() > self._header_h else math.nan
        self.contextRequested.emit(idx, depth, e.globalPos())

    def _external_cursor(self, md: float):
        """Cursor moved from another view of the same well (e.g. the data table)."""
        if self.underMouse():
            return
        self._set_cursor_y(None if math.isnan(md) else self.y_of(float(self.well.to_display(md))))

    def visible_depth_range(self) -> tuple[float, float]:
        tf = self.transform()
        return tf.depth(0), tf.depth(self.body_h)

    def readout(self, md: float) -> str:
        """Text with the depth (MD, plus TVD/TVDSS when known) and visible curve values at a depth."""
        well = self.doc.well
        unit = well.depth_unit
        parts = [f"MD {md:.2f} {unit}"]
        if well.survey is not None or self.doc.depth_reference != "md":
            tvd = float(np.interp(md, well.depth, well.tvd()))
            parts.append(f"TVD {tvd:.2f} {unit}")
            if well.elevation is not None:
                parts.append(f"TVDSS {tvd - well.elevation:.2f} {unit}")
        seen = set()
        for t in self.doc.layout.tracks:
            for c in t.curves:
                if c.visible and c.mnemonic in well.curves and c.mnemonic not in seen:
                    seen.add(c.mnemonic)
                    v = well.value_at(c.mnemonic, md)
                    if np.isfinite(v):
                        curve_unit = well.curves[c.mnemonic].unit
                        parts.append(f"{c.mnemonic} {v:.4g}{(' ' + curve_unit) if curve_unit else ''}")
        for top in sorted(well.tops, key=lambda t: t.depth, reverse=True):
            if top.depth <= md:
                parts.insert(1, _("Zone: {name}").format(name=top.name))
                break
        return "   |   ".join(parts)
