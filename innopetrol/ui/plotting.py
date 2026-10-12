"""Drawing helpers for simple charts (axes, ticks) with QPainter."""

from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPen

from innopetrol.model.scales import log_grid_positions, map_values
from innopetrol.render.painter import BORDER, GRID_MAJOR, GRID_MINOR, fmt

VIRIDIS = ["#440154", "#482878", "#3e4989", "#31688e", "#26828e", "#1f9e89", "#35b779", "#6ece58", "#b5de2b",
           "#fde725"]


def colormap(t: np.ndarray) -> list[QColor]:
    stops = [QColor(c) for c in VIRIDIS]
    out = []
    for v in np.clip(np.nan_to_num(t, nan=0.0), 0, 1):
        x = v * (len(stops) - 1)
        i = min(int(x), len(stops) - 2)
        f = x - i
        a, b = stops[i], stops[i + 1]
        out.append(QColor(int(a.red() + (b.red() - a.red()) * f), int(a.green() + (b.green() - a.green()) * f),
                          int(a.blue() + (b.blue() - a.blue()) * f)))
    return out


def linear_ticks(lo: float, hi: float, n: int = 6) -> list[float]:
    a, b = sorted((lo, hi))
    span = b - a
    if span <= 0 or not math.isfinite(span):
        return [a]
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    start = math.ceil(a / step) * step
    return [round(start + i * step, 10) for i in range(int((b - start) / step + 1e-9) + 1)]


class Axis:
    def __init__(self, lo: float, hi: float, log: bool, label: str):
        self.lo, self.hi, self.log, self.label = lo, hi, log, label

    def map(self, values, length: float) -> np.ndarray:
        return map_values(values, self.lo, self.hi, self.log, length)

    def value_at(self, pos: float, length: float) -> float:
        """Inverse of map(): the value at a position along the axis (0 = lo, length = hi)."""
        t = pos / length if length else 0.0
        if self.log:
            lo, hi = math.log10(self.lo), math.log10(self.hi)
            return 10 ** (lo + t * (hi - lo))
        return self.lo + t * (self.hi - self.lo)

    def ticks(self) -> list[tuple[float, bool]]:
        if self.log:
            return [(v, d) for v, d in log_grid_positions(self.lo, self.hi)]
        return [(v, True) for v in linear_ticks(self.lo, self.hi)]


def plot_rect(widget_rect: QRectF, fm: QFontMetricsF) -> QRectF:
    left = fm.horizontalAdvance("00000.0") + fm.height() + 10
    bottom = fm.height() * 2.6
    return QRectF(widget_rect.left() + left, widget_rect.top() + 10,
                  widget_rect.width() - left - 16, widget_rect.height() - bottom - 10)


def draw_axes(p: QPainter, r: QRectF, xa: Axis, ya: Axis) -> None:
    fm = QFontMetricsF(p.font())
    p.fillRect(r, Qt.white)
    for axis, horizontal in ((xa, True), (ya, False)):
        for v, major in axis.ticks():
            if horizontal:
                x = r.left() + float(axis.map(np.array([v]), r.width())[0])
                p.setPen(QPen(GRID_MAJOR if major else GRID_MINOR, 0.8))
                p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
                if major:
                    p.setPen(BORDER)
                    p.drawText(QRectF(x - 40, r.bottom() + 2, 80, fm.height()), Qt.AlignHCenter, fmt(v))
            else:
                y = r.bottom() - float(axis.map(np.array([v]), r.height())[0])
                p.setPen(QPen(GRID_MAJOR if major else GRID_MINOR, 0.8))
                p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
                if major:
                    p.setPen(BORDER)
                    p.drawText(QRectF(r.left() - 64, y - fm.height() / 2, 60, fm.height()),
                               Qt.AlignRight | Qt.AlignVCenter, fmt(v))
    p.setPen(QPen(BORDER, 1))
    p.setBrush(Qt.NoBrush)
    p.drawRect(r)
    p.drawText(QRectF(r.left(), r.bottom() + fm.height() + 2, r.width(), fm.height()), Qt.AlignCenter, xa.label)
    p.save()
    p.translate(r.left() - fm.horizontalAdvance("00000.0") - fm.height() - 4, r.center().y())
    p.rotate(-90)
    p.drawText(QRectF(-r.height() / 2, 0, r.height(), fm.height()), Qt.AlignCenter, ya.label)
    p.restore()
