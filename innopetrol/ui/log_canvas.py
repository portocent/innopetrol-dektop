"""LogCanvas: widget interactivo que dibuja un pozo completo (encabezados + tracks).

Navegación:
  rueda            desplaza en profundidad
  Ctrl + rueda     zoom alrededor del cursor
  Shift + rueda    desplaza horizontalmente
  RePág/AvPág, Inicio/Fin, flechas
  arrastrar el borde de un track cambia su ancho; doble clic en un track lo edita.
"""

from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from innopetrol.model.scales import px_per_unit, scale_ratio
from innopetrol.render.painter import BORDER, DepthTransform, RenderOptions, header_height
from innopetrol.render.scene import paint_headers, paint_log, paint_tops_overlay, track_edges, total_width
from innopetrol.ui.document import WellDocument
from innopetrol.ui.tile_cache import TILE_H, TileCache

MIN_TRACK_W = 40
EDGE_GRAB = 4


class LogCanvas(QWidget):
    viewChanged = Signal()
    trackActivated = Signal(int)
    contextRequested = Signal(int, float, object)  # índice de track (-1 = ninguno), profundidad, pos global
    selectionChanged = Signal(int)

    def __init__(self, doc: WellDocument, parent=None, show_top_labels: bool = True):
        super().__init__(parent)
        self.doc = doc
        self.show_top_labels = show_top_labels
        self.ppu = 1.0
        self.top = doc.well.start
        self.x_offset = 0.0
        self.fit_mode = True
        self.depth_shift = 0.0  # para correlación: se suma a la profundidad mostrada
        self.selected = -1
        self._cursor_y: float | None = None
        self._drag: tuple[int, float, int] | None = None  # (track, x inicial, ancho inicial)
        self._header_h = 60.0
        self.min_header_h = 0.0  # en correlación todos los pozos usan el mismo alto de encabezado
        self.clamp_enabled = True
        self._version = 0  # aumenta con cada cambio de layout: invalida la caché
        self._tiles = TileCache()
        self._header_pm: QPixmap | None = None
        self._header_key = None
        self._prefetch = QTimer(self)
        self._prefetch.setSingleShot(True)
        self._prefetch.timeout.connect(self._prefetch_tiles)
        self.setAttribute(Qt.WA_OpaquePaintEvent)  # pintamos todo el fondo: Qt no necesita borrarlo
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(200, 200)
        self.setAutoFillBackground(False)
        doc.layoutChanged.connect(self._layout_changed)
        doc.cursorMoved.connect(self._external_cursor)

    # ------------------------------------------------------------------ geometría y escala

    @property
    def well(self):
        return self.doc.well

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

    def zoom(self, factor: float, anchor_depth: float | None = None) -> None:
        self.fit_mode = False
        self._set_ppu(self.ppu * factor, anchor_depth)

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
        """Rango permitido para la profundidad superior visible."""
        pad = 20 / self.ppu
        lo = self.well.start - pad + self.depth_shift
        hi = max(lo, self.well.stop + pad - self.body_h / self.ppu + self.depth_shift)
        return lo, hi

    def set_view(self, top: float, ppu: float) -> None:
        """Fija vista sin recalcular anclas (usado para sincronizar varios pozos)."""
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
        """Descarta los dibujos en caché (llamar cuando cambia algo que se ve en el registro)."""
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
        # depth_shift desplaza el pozo (aplanar en un tope durante la correlación)
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
        """Índice del track cuyo borde derecho está bajo x (para redimensionar)."""
        for i, (tx, w) in enumerate(track_edges(self.doc.layout)):
            if abs(tx + w - self.x_offset - x) <= EDGE_GRAB:
                return i
        return -1

    # ------------------------------------------------------------------ eventos Qt

    def showEvent(self, e):
        super().showEvent(e)
        self._layout_changed()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.fit_mode:
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
        p.end()
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
        base = tf.top * self.ppu  # y absoluta (en píxeles) del borde superior del cuerpo
        return math.floor(base / TILE_H), math.floor((base + self.body_h) / TILE_H), base

    def _paint_body(self, p: QPainter, tf: DepthTransform):
        width = total_width(self.doc.layout)
        if width <= 0:
            return
        self._tiles.validate((self._version, self.ppu, self._dpr(), self.font().key()))
        k0, k1, base = self._tile_range(tf)
        p.save()
        p.setClipRect(QRectF(0, self._header_h, self.width(), self.body_h))
        for k in range(k0, k1 + 1):
            pm = self._tile(k)
            p.drawPixmap(QPointF(-self.x_offset, round(self._header_h + k * TILE_H - base)), pm)
        p.restore()

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
        paint_log(tp, self.doc.layout, self.well, tf, 0, 0, 0, TILE_H, opts, draw_headers=False)
        tp.end()
        return pm

    def _prefetch_tiles(self):
        """Con la aplicación inactiva, dibuja por adelantado el tile de arriba y el de abajo."""
        if not self.isVisible() or total_width(self.doc.layout) <= 0:
            return
        k0, k1, _ = self._tile_range(self.transform())
        for k in (k1 + 1, k0 - 1):
            if k not in self._tiles:
                self._tiles.put(k, self._render_tile(k))
                self._prefetch.start(0)  # de a uno por vez para no bloquear la interfaz
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
            self.zoom(1.2 ** steps, anchor)
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
            self.zoom(1.25)
        elif key == Qt.Key_Minus:
            self.zoom(0.8)
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
            self.doc.layout.tracks[i].width = int(max(MIN_TRACK_W, w0 + x - x0))
            self.invalidate()
            return
        self.setCursor(Qt.SplitHCursor if self._edge_at(x) >= 0 else Qt.ArrowCursor)
        if y > self._header_h and self.track_at(x) >= 0:
            self._set_cursor_y(y)
            self.doc.cursorMoved.emit(self.depth_at(y))
        else:
            self._set_cursor_y(None)
            self.doc.cursorMoved.emit(math.nan)

    def _cursor_rect(self, y: float | None) -> QRect | None:
        if y is None:
            return None
        fm_h = QFontMetricsF(self.font()).height()
        return QRect(0, int(y - fm_h - 4), self.width(), int(fm_h + 8))

    def _set_cursor_y(self, y: float | None):
        """Mueve la línea del cursor repintando sólo las franjas afectadas, no todo el widget."""
        if y == self._cursor_y:
            return
        for rect in (self._cursor_rect(self._cursor_y), self._cursor_rect(y)):
            if rect is not None:
                self.update(rect)
        self._cursor_y = y

    def mouseReleaseEvent(self, e):
        if self._drag:
            self._drag = None
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

    def _external_cursor(self, depth: float):
        """Cursor movido desde otra vista del mismo pozo (p. ej. la tabla de datos)."""
        if self.underMouse():
            return
        self._set_cursor_y(None if math.isnan(depth) else self.y_of(depth))

    def visible_depth_range(self) -> tuple[float, float]:
        tf = self.transform()
        return tf.depth(0), tf.depth(self.body_h)

    def readout(self, depth: float) -> str:
        """Texto con los valores de las curvas visibles en una profundidad."""
        parts = [f"{self.well.depth_mnemonic} {depth:.2f} {self.well.depth_unit}"]
        seen = set()
        for t in self.doc.layout.tracks:
            for c in t.curves:
                if c.visible and c.mnemonic in self.well.curves and c.mnemonic not in seen:
                    seen.add(c.mnemonic)
                    v = self.well.value_at(c.mnemonic, depth)
                    if np.isfinite(v):
                        unit = self.well.curves[c.mnemonic].unit
                        parts.append(f"{c.mnemonic} {v:.4g}{(' ' + unit) if unit else ''}")
        for top in reversed(self.well.tops):
            if top.depth <= depth:
                parts.insert(1, f"Zona: {top.name}")
                break
        return "   |   ".join(parts)
