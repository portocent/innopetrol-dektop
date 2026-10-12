"""Graphical parameter picking: clean/shale GR on a histogram and Rw on a Pickett plot.

Typing parameters by hand is error-prone; engineers pick them where the data shows them. Both
pickers keep a spin box synchronized with the line on the chart, so a value can be dragged and
then refined by typing.
"""

from __future__ import annotations

import math
from itertools import pairwise

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from innopetrol.i18n import _
from innopetrol.model.scales import log_decades
from innopetrol.render.painter import polygon_from_arrays
from innopetrol.resources import app_icon
from innopetrol.ui.analysis import Histogram
from innopetrol.ui.plotting import Axis, draw_axes, plot_rect
from innopetrol.ui.widgets import spin

GRAB_PX = 8  # how close to a line the mouse must be to grab it
CLEAN_COLOR, SHALE_COLOR = "#1e8449", "#8e5a2b"


# ============================================================================ GR histogram


class GrPickHistogram(Histogram):
    """Histogram with two vertical lines (clean and shale GR) that can be dragged."""

    linesChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lines = {"clean": 0.0, "shale": 0.0}
        self._drag: str | None = None
        self.setMouseTracking(True)

    def paint_overlay(self, p, r, xa):
        fm = QFontMetricsF(self.font())
        for key, color, text in (("clean", CLEAN_COLOR, _("Clean")), ("shale", SHALE_COLOR, _("Shale"))):
            x = self._x(key)
            if x is None:
                continue
            p.setPen(QPen(QColor(color), 2.5 if key == self._drag else 2))
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
            label = f"{text} {self.lines[key]:.1f}"
            w = fm.horizontalAdvance(label) + 8
            box = QRectF(min(max(x - w / 2, r.left()), r.right() - w), r.top() + 2, w, fm.height() + 2)
            p.fillRect(box, QColor(255, 255, 255, 220))
            p.drawText(box, Qt.AlignCenter, label)

    def _x(self, key: str) -> float | None:
        r, xa = self.plot_area, self.x_axis
        if xa is None:
            return None
        x = xa.map_one(self.lines[key], r.width())
        return r.left() + x if math.isfinite(x) else None

    def _value(self, x: float) -> float:
        r, xa = self.plot_area, self.x_axis
        if xa is None:
            return 0.0
        return xa.value_at(min(max(x, r.left()), r.right()) - r.left(), r.width())

    def _nearest(self, x: float) -> str | None:
        dist = {k: abs(px - x) for k in self.lines if (px := self._x(k)) is not None}
        return min(dist, key=lambda k: dist[k]) if dist else None

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton or self.x_axis is None:
            return
        x = e.position().x()
        # A click away from the lines moves the nearest one there: quicker than dragging.
        self._drag = self._nearest(x)
        if self._drag:
            self.lines[self._drag] = round(self._value(x), 1)
            self.update()
            self.linesChanged.emit()

    def mouseMoveEvent(self, e):
        x = e.position().x()
        if self._drag:
            self.lines[self._drag] = round(self._value(x), 1)
            self.update()
            self.linesChanged.emit()
            return
        key = self._nearest(x)
        near = key is not None and abs(self._x(key) - x) <= GRAB_PX
        self.setCursor(Qt.SplitHCursor if near else Qt.ArrowCursor)

    def mouseReleaseEvent(self, e):
        self._drag = None
        self.update()


class GrPickerDialog(QDialog):
    """Picks clean and shale GR on the histogram of an interval."""

    def __init__(self, values: np.ndarray, clean: float, shale: float, label: str, interval: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Pick clean and shale GR — {interval}").format(interval=interval))
        self.setWindowIcon(app_icon())
        self.resize(640, 460)
        self.values = np.asarray(values, float)
        self.values = self.values[np.isfinite(self.values)]
        lay = QVBoxLayout(self)
        hint = QLabel(
            _(
                "Drag the green line to the clean sand and the brown line to the shale, or click "
                "near a line to move it there. P5/P95 places them at the 5th and 95th percentiles."
            )
        )
        hint.setWordWrap(True)
        lay.addWidget(hint)
        self.hist = GrPickHistogram()
        self.hist.set_data(self.values, label, False, 60, "#95a5a6")
        lay.addWidget(self.hist, 1)
        row = QHBoxLayout()
        self.clean = spin(clean, -1000, 10000, 1, 1)
        self.shale = spin(shale, -1000, 10000, 1, 1)
        row.addWidget(QLabel(_("Clean GR")))
        row.addWidget(self.clean)
        row.addWidget(QLabel(_("Shale GR")))
        row.addWidget(self.shale)
        auto = QPushButton(_("P5 / P95"))
        auto.clicked.connect(self._percentiles)
        row.addWidget(auto)
        row.addStretch()
        lay.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.clean.valueChanged.connect(self._from_spins)
        self.shale.valueChanged.connect(self._from_spins)
        self.hist.linesChanged.connect(self._from_lines)
        self._from_spins()

    def _from_spins(self):
        self.hist.lines = {"clean": self.clean.value(), "shale": self.shale.value()}
        self.hist.update()

    def _from_lines(self):
        for box, key in ((self.clean, "clean"), (self.shale, "shale")):
            box.blockSignals(True)
            box.setValue(self.hist.lines[key])
            box.blockSignals(False)

    def _percentiles(self):
        if self.values.size:
            lo, hi = np.percentile(self.values, [5, 95])
            self.clean.setValue(round(float(lo), 1))
            self.shale.setValue(round(float(hi), 1))

    def _accept(self):
        if self.clean.value() >= self.shale.value():
            QMessageBox.warning(self, self.windowTitle(), _("Clean GR must be lower than shale GR."))
            return
        self.accept()

    def result_values(self) -> tuple[float, float]:
        return self.clean.value(), self.shale.value()


# ============================================================================ Pickett


class PickettPicker(QWidget):
    """Log-log Rt (x) vs porosity (y) with Sw lines; the Sw = 1 (water) line is dragged to set Rw.

    Archie: Rt = a·Rw / (φ^m · Sw^n). On log-log axes every Sw is a straight line of slope −1/m;
    moving the water line parallel to itself changes Rw.
    """

    rwChanged = Signal(float)

    SHALY = 0.35  # Vsh above which a point is drawn faded and ignored by the automatic fit

    def __init__(self, rt: np.ndarray, phi: np.ndarray, vsh: np.ndarray | None = None, parent=None):
        super().__init__(parent)
        ok = np.isfinite(rt) & np.isfinite(phi) & (rt > 0) & (phi > 0)
        self.rt, self.phi = rt[ok], phi[ok]
        # Shale also has low resistivity: without Vsh every point is treated as clean.
        self.clean = np.ones(self.rt.shape, bool) if vsh is None else ~(np.asarray(vsh)[ok] > self.SHALY)
        self.rw, self.a, self.m, self.n = 0.05, 1.0, 2.0, 2.0
        lo, hi = log_decades(float(self.rt.min()), float(self.rt.max())) if self.rt.size else (0.1, 1000.0)
        self.xa = Axis(lo, hi, True, "Rt (ohm·m)")
        self.ya = Axis(0.01, 1.0, True, "φe (v/v)")
        self._drag = False
        self.setMinimumSize(520, 420)
        self.setMouseTracking(True)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#f7f8f9"))
        fm = QFontMetricsF(self.font())
        r = self.plot_area
        draw_axes(p, r, self.xa, self.ya)
        p.save()
        p.setClipRect(r)
        if self.rt.size:
            xs = r.left() + self.xa.map(self.rt, r.width())
            ys = r.bottom() - self.ya.map(self.phi, r.height())
            for sel, color in ((~self.clean, "#d5d8dc"), (self.clean, "#34495e")):
                if sel.any():
                    p.setPen(QPen(QColor(color), 2.5))
                    p.drawPoints(polygon_from_arrays(xs[sel], ys[sel]))
        phi = np.logspace(-2, 0, 60)
        for sw, color, width in ((1.0, "#1a5276", 2.6), (0.5, "#27ae60", 1.4), (0.25, "#c0392b", 1.4)):
            rt = self.a * self.rw / (phi**self.m * sw**self.n)
            xs = r.left() + self.xa.map(rt, r.width())
            ys = r.bottom() - self.ya.map(phi, r.height())
            pen = QPen(QColor(color), width + (1 if sw == 1 and self._drag else 0))
            if sw < 1:
                pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            pts = [QPointF(x, y) for x, y in zip(xs, ys, strict=True) if math.isfinite(x) and math.isfinite(y)]
            for a, b in pairwise(pts):
                p.drawLine(a, b)
            inside = [q for q in pts if r.contains(q)]
            if inside:
                q = inside[len(inside) // 3]
                p.drawText(q + QPointF(6, -4), f"Sw={sw:g}")
        p.restore()
        p.setPen(QColor("#1a5276"))
        p.drawText(
            QRectF(r.left() + 8, r.top() + 4, r.width() - 16, fm.height() * 1.3),
            Qt.AlignRight,
            f"Rw = {self.rw:.4g}  ·  a = {self.a:g}  ·  m = {self.m:g}  ·  n = {self.n:g}",
        )
        p.end()

    @property
    def plot_area(self) -> QRectF:
        return plot_rect(QRectF(self.rect()), QFontMetricsF(self.font()))

    def _rw_at(self, pos: QPointF) -> float | None:
        r = self.plot_area
        if not r.contains(pos):
            return None
        rt = self.xa.value_at(pos.x() - r.left(), r.width())
        phi = self.ya.value_at(r.bottom() - pos.y(), r.height())
        return rt * phi**self.m / self.a  # the water line through this point

    def _near_water_line(self, pos: QPointF) -> bool:
        r = self.plot_area
        if not r.contains(pos):
            return False
        phi = self.ya.value_at(r.bottom() - pos.y(), r.height())
        rt = self.a * self.rw / phi**self.m
        x = r.left() + self.xa.map_one(rt, r.width())
        return math.isfinite(x) and abs(x - pos.x()) <= GRAB_PX

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            rw = self._rw_at(e.position())
            if rw is not None:
                self._drag = True
                self.set_rw(rw)

    def mouseMoveEvent(self, e):
        if self._drag:
            rw = self._rw_at(e.position())
            if rw is not None:
                self.set_rw(rw)
            return
        self.setCursor(Qt.SizeAllCursor if self._near_water_line(e.position()) else Qt.ArrowCursor)

    def mouseReleaseEvent(self, e):
        self._drag = False
        self.update()

    def set_rw(self, rw: float, notify: bool = True):
        self.rw = float(f"{rw:.4g}")
        self.update()
        if notify:
            self.rwChanged.emit(self.rw)

    def fit_water_line(self) -> float | None:
        """Rw that places the water line along the lowest-resistivity points (the wettest rock).

        Each clean point gives an apparent Rw = Rt·φ^m/a (Archie with Sw = 1); water-bearing rock has
        the lowest values. The 5th percentile is used instead of the minimum to ignore outliers.
        """
        ok = self.clean & (self.phi >= 0.05)  # shale and tight rock would pull the line down
        if ok.sum() < 10:
            return None
        rwa = self.rt[ok] * self.phi[ok] ** self.m / self.a
        return float(np.percentile(rwa, 5))


class PickettPickerDialog(QDialog):
    def __init__(
        self,
        rt: np.ndarray,
        phi: np.ndarray,
        rw: float,
        a: float,
        m: float,
        n: float,
        interval: str,
        vsh: np.ndarray | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(_("Pick Rw on the Pickett plot — {interval}").format(interval=interval))
        self.setWindowIcon(app_icon())
        self.resize(720, 600)
        lay = QVBoxLayout(self)
        hint = QLabel(
            _(
                "Drag the blue water line (Sw = 1) onto the lowest-resistivity points, which are "
                "usually water-bearing. The slope depends on m. “Fit to the wettest points” "
                "places it automatically."
            )
        )
        hint.setWordWrap(True)
        lay.addWidget(hint)
        self.plot = PickettPicker(rt, phi, vsh)
        self.plot.a, self.plot.m, self.plot.n = a, m, n
        self.plot.set_rw(rw, notify=False)
        lay.addWidget(self.plot, 1)
        row = QHBoxLayout()
        self.rw = spin(rw, 0.001, 100, 0.005, 4)
        self.a = spin(a, 0.1, 5, 0.01, 3)
        self.m = spin(m, 1, 4, 0.05, 3)
        self.n = spin(n, 1, 4, 0.05, 3)
        for text, box in (("Rw", self.rw), ("a", self.a), ("m", self.m), ("n", self.n)):
            row.addWidget(QLabel(text))
            row.addWidget(box)
            box.valueChanged.connect(self._from_spins)
        fit = QPushButton(_("Fit to the wettest points"))
        fit.clicked.connect(self._fit)
        row.addWidget(fit)
        row.addStretch()
        lay.addLayout(row)
        text = _("{count} points with φ and Rt").format(count=self.plot.rt.size)
        if vsh is not None:
            text += " · " + _("light gray: shaly (Vsh > {cutoff}), not used by the automatic fit").format(
                cutoff=f"{PickettPicker.SHALY:g}"
            )
        self.points_label = QLabel(text)
        self.points_label.setStyleSheet("color: #566573")
        lay.addWidget(self.points_label)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.plot.rwChanged.connect(self._from_plot)

    def _from_spins(self):
        self.plot.a, self.plot.m, self.plot.n = self.a.value(), self.m.value(), self.n.value()
        self.plot.set_rw(self.rw.value(), notify=False)

    def _from_plot(self, rw: float):
        self.rw.blockSignals(True)
        self.rw.setValue(rw)
        self.rw.blockSignals(False)

    def _fit(self):
        rw = self.plot.fit_water_line()
        if rw is not None:
            self.rw.setValue(rw)

    def result_values(self) -> tuple[float, float, float, float]:
        return self.rw.value(), self.a.value(), self.m.value(), self.n.value()
