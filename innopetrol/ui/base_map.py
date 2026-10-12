"""Base map: wells at their surface location with their trajectories; pick a correlation section.

Clicking wells selects them in order (the order of the correlation section); double-clicking opens
the well's window. Drag to pan, wheel to zoom.
"""

from __future__ import annotations

import math
from itertools import pairwise

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from innopetrol.i18n import _
from innopetrol.model.location import trajectory
from innopetrol.render.painter import BORDER, GRID_MAJOR, fmt
from innopetrol.resources import app_icon
from innopetrol.ui.plotting import linear_ticks

PICK_PX = 10
SELECTED = QColor("#e67e22")


class MapItem:
    def __init__(self, doc):
        self.doc = doc
        loc = doc.well.location
        self.location = loc
        self.xs, self.ys = trajectory(loc, doc.well.survey, doc.well.depth_unit)


class BaseMapWidget(QWidget):
    selectionChanged = Signal()
    wellActivated = Signal(object)  # WellDocument
    cursorText = Signal(str)  # map coordinates under the mouse

    def __init__(self, items: list[MapItem], geographic: bool, parent=None):
        super().__init__(parent)
        self.items = items
        self.geographic = geographic
        self.selected: list[MapItem] = []
        # Geographic coordinates are drawn with longitude scaled by cos(latitude), so that a
        # kilometer east and a kilometer north have the same length on screen.
        lat0 = np.mean([i.location.y for i in items]) if items and geographic else 0.0
        self.kx = math.cos(math.radians(lat0)) if geographic else 1.0
        self.center = QPointF(0, 0)
        self.ppu = 1.0  # pixels per map unit
        self._press: QPointF | None = None
        self._moved = False
        self.setMinimumSize(500, 400)
        self.setMouseTracking(True)

    # ---------------------------------------------------------------- coordinates
    def _bounds(self) -> tuple[float, float, float, float]:
        xs = np.concatenate([i.xs for i in self.items]) * self.kx
        ys = np.concatenate([i.ys for i in self.items])
        return float(np.min(xs)), float(np.max(xs)), float(np.min(ys)), float(np.max(ys))

    def fit(self):
        if not self.items:
            return
        x0, x1, y0, y1 = self._bounds()
        span = max(x1 - x0, y1 - y0)
        if span <= 0:  # a single vertical well: show about a kilometer around it
            span = 0.01 if self.geographic else 1000.0
        self.center = QPointF((x0 + x1) / 2, (y0 + y1) / 2)
        self.ppu = min(self.width(), self.height()) * 0.8 / (span * 1.1)
        self.update()

    def to_screen(self, x, y) -> tuple[np.ndarray, np.ndarray]:
        sx = self.width() / 2 + (np.asarray(x) * self.kx - self.center.x()) * self.ppu
        sy = self.height() / 2 - (np.asarray(y) - self.center.y()) * self.ppu
        return sx, sy

    def to_map(self, p: QPointF) -> tuple[float, float]:
        x = (p.x() - self.width() / 2) / self.ppu + self.center.x()
        y = (self.height() / 2 - p.y()) / self.ppu + self.center.y()
        return x / self.kx, y

    def item_at(self, p: QPointF) -> MapItem | None:
        best: MapItem | None = None
        best_d = float(PICK_PX)
        for item in self.items:
            sx, sy = self.to_screen(item.location.x, item.location.y)
            d = math.hypot(float(sx) - p.x(), float(sy) - p.y())
            if d <= best_d:
                best, best_d = item, d
        return best

    # ---------------------------------------------------------------- drawing
    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.ppu == 1.0:
            self.fit()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#fbfcfc"))
        self._draw_grid(p)
        fm = QFontMetricsF(self.font())
        for item in self.items:
            sx, sy = self.to_screen(item.xs, item.ys)
            if item.xs.size > 1:
                p.setPen(QPen(QColor("#5d6d7e"), 1.6))
                for i in range(item.xs.size - 1):
                    p.drawLine(QPointF(sx[i], sy[i]), QPointF(sx[i + 1], sy[i + 1]))
                p.setBrush(QColor("#5d6d7e"))
                p.drawEllipse(QPointF(sx[-1], sy[-1]), 2.5, 2.5)  # bottom of the hole
        if len(self.selected) > 1:  # the correlation section
            pts = [self.to_screen(i.location.x, i.location.y) for i in self.selected]
            p.setPen(QPen(SELECTED, 2.2, Qt.PenStyle.DashLine))
            for (ax, ay), (bx, by) in pairwise(pts):
                p.drawLine(QPointF(ax, ay), QPointF(bx, by))
        bold = QFont(self.font())
        bold.setBold(True)
        for item in self.items:
            sx, sy = (float(v) for v in self.to_screen(item.location.x, item.location.y))
            chosen = item in self.selected
            p.setPen(QPen(BORDER, 1.2))
            p.setBrush(SELECTED if chosen else QColor("#2e86c1"))
            p.drawEllipse(QPointF(sx, sy), 6 if chosen else 5, 6 if chosen else 5)
            p.setFont(bold if chosen else self.font())
            label = item.doc.title
            if chosen:
                label = f"{self.selected.index(item) + 1}. {label}"
            w = QFontMetricsF(p.font()).horizontalAdvance(label) + 6
            box = QRectF(sx + 8, sy - fm.height() - 2, w, fm.height())
            p.fillRect(box, QColor(255, 255, 255, 200))
            p.setPen(BORDER)
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, label)
        p.end()

    def _draw_grid(self, p: QPainter):
        fm = QFontMetricsF(self.font())
        x0, y0 = self.to_map(QPointF(0, self.height()))
        x1, y1 = self.to_map(QPointF(self.width(), 0))
        p.setFont(self.font())
        for v in linear_ticks(x0, x1, max(int(self.width() / 120), 2)):
            sx = float(self.to_screen(v, 0)[0])
            p.setPen(QPen(GRID_MAJOR, 0.6))
            p.drawLine(QPointF(sx, 0), QPointF(sx, self.height()))
            p.setPen(QColor("#566573"))
            p.drawText(
                QRectF(sx - 60, self.height() - fm.height() - 2, 120, fm.height()),
                Qt.AlignmentFlag.AlignCenter,
                self._label(v),
            )
        for v in linear_ticks(y0, y1, max(int(self.height() / 90), 2)):
            sy = float(self.to_screen(0, v)[1])
            p.setPen(QPen(GRID_MAJOR, 0.6))
            p.drawLine(QPointF(0, sy), QPointF(self.width(), sy))
            p.setPen(QColor("#566573"))
            p.drawText(
                QRectF(4, sy - fm.height(), 140, fm.height()),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
                self._label(v),
            )

    def _label(self, v: float) -> str:
        return f"{v:.4f}°" if self.geographic else fmt(v)

    # ---------------------------------------------------------------- interaction
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._press = e.position()
            self._moved = False

    def mouseMoveEvent(self, e):
        if self._press is not None:
            d = e.position() - self._press
            if self._moved or abs(d.x()) + abs(d.y()) > 3:
                self._moved = True
                self.center -= QPointF(d.x(), -d.y()) / self.ppu
                self._press = e.position()
                self.update()
            return
        self.setCursor(Qt.CursorShape.PointingHandCursor if self.item_at(e.position()) else Qt.CursorShape.ArrowCursor)
        x, y = self.to_map(e.position())
        self.cursorText.emit(
            _("Lat {lat} · Lon {lon}").format(lat=f"{y:.5f}°", lon=f"{x:.5f}°")
            if self.geographic
            else f"X {x:.1f} · Y {y:.1f}"
        )

    def mouseReleaseEvent(self, e):
        if self._press is not None and not self._moved:
            item = self.item_at(e.position())
            if item is not None:
                if item in self.selected:
                    self.selected.remove(item)
                else:
                    self.selected.append(item)
                self.selectionChanged.emit()
                self.update()
        self._press = None

    def mouseDoubleClickEvent(self, e):
        item = self.item_at(e.position())
        if item is not None:
            self.wellActivated.emit(item.doc)

    def wheelEvent(self, e):
        factor = 1.0015 ** e.angleDelta().y()
        before = self.to_map(e.position())
        self.ppu *= factor
        after = self.to_map(e.position())
        self.center += QPointF((before[0] - after[0]) * self.kx, before[1] - after[1])
        self.update()


class BaseMapWindow(QDialog):
    correlateRequested = Signal(list)  # WellDocuments in section order
    wellActivated = Signal(object)

    def __init__(self, docs, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Base map"))
        self.setWindowIcon(app_icon())
        self.resize(900, 700)
        located = [d for d in docs if d.well.location is not None]
        n_geo = sum(d.well.location.geographic for d in located)
        geographic = n_geo >= len(located) - n_geo
        shown = [d for d in located if d.well.location.geographic == geographic]
        other_system = [d for d in located if d not in shown]
        missing = [d for d in docs if d.well.location is None]

        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        hint = QLabel(
            _(
                "Click wells in order to draw a correlation section · double-click opens a well · "
                "drag to pan, wheel to zoom"
            )
        )
        hint.setStyleSheet("color:#566573")
        bar.addWidget(hint, 1)
        fit = QPushButton(_("Fit"))
        clear = QPushButton(_("Clear selection"))
        self.correlate = QPushButton()
        for b in (fit, clear, self.correlate):
            bar.addWidget(b)
        lay.addLayout(bar)
        self.map = BaseMapWidget([MapItem(d) for d in shown], geographic)
        lay.addWidget(self.map, 1)
        notes = []
        if missing:
            notes.append(
                _(
                    "Without coordinates (enter them in Well ▸ Deviation survey, elevation and location…): {wells}"
                ).format(wells=", ".join(d.title for d in missing))
            )
        if other_system:
            notes.append(
                _("Not shown, coordinates of another type (projected vs. latitude/longitude): {wells}").format(
                    wells=", ".join(d.title for d in other_system)
                )
            )
        self.coords = QLabel(" ")
        self.coords.setStyleSheet("color:#566573")
        lay.addWidget(self.coords)
        self.map.cursorText.connect(self.coords.setText)
        if notes:
            note = QLabel("\n".join(notes))
            note.setWordWrap(True)
            note.setStyleSheet("color:#b9770e")
            lay.addWidget(note)
        fit.clicked.connect(self.map.fit)
        clear.clicked.connect(self._clear)
        self.correlate.clicked.connect(lambda: self.correlateRequested.emit([i.doc for i in self.map.selected]))
        self.map.selectionChanged.connect(self._update_button)
        self.map.wellActivated.connect(self.wellActivated)
        self._update_button()

    def _clear(self):
        self.map.selected.clear()
        self.map.update()
        self._update_button()

    def _update_button(self):
        n = len(self.map.selected)
        self.correlate.setText(_("Correlate selected ({count})").format(count=n))
        self.correlate.setEnabled(n >= 2)
