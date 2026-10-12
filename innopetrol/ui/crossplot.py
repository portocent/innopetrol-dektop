"""Crossplot of two curves colored by a third one. Neutron-density and Pickett modes."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QImage, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QWidget)

from innopetrol.i18n import N_, _
from innopetrol.model.mnemonics import default_scale, find_curve
from innopetrol.model.petro import PetroParams
from innopetrol.model.scales import log_decades, nice_linear_range
from innopetrol.render.painter import BORDER, fmt, polygon_from_arrays
from innopetrol.resources import app_icon
from innopetrol.ui.analysis import zone_choices
from innopetrol.ui.document import WellDocument
from innopetrol.ui.plotting import Axis, colormap, draw_axes, plot_rect
from innopetrol.ui.widgets import parse_float

# Approximate lithology lines for a limestone-calibrated neutron: (φN, ρb) as a function of φ.
LITHOLOGY = {
    N_("Sandstone"): (lambda f: f - 0.035 * (1 - f / 0.45), lambda f: 2.65 - 1.65 * f, "#d4ac0d"),
    N_("Limestone"): (lambda f: f, lambda f: 2.71 - 1.71 * f, "#2471a3"),
    N_("Dolomite"): (lambda f: f + 0.04 + 0.05 * f, lambda f: 2.87 - 1.87 * f, "#7d3c98"),
}


N_LEVELS = 32


def _points(x: np.ndarray, y: np.ndarray):
    return polygon_from_arrays(x, y)


class CrossplotWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(520, 420)
        self.x = self.y = self.c = np.array([])
        self.xa = Axis(0, 1, False, "")
        self.ya = Axis(0, 1, False, "")
        self.c_range = (0.0, 1.0)
        self.c_label = ""
        self.overlay = None  # "nd" | "pickett"
        self.neutron_scale = 1.0
        self.pickett: PetroParams | None = None

    def paintEvent(self, e):
        p = QPainter(self)
        self.paint_plot(p, QRectF(self.rect()))
        p.end()

    def paint_plot(self, p: QPainter, area: QRectF):
        p.fillRect(area, QColor("#f7f8f9"))
        p.setRenderHint(QPainter.Antialiasing)
        fm = QFontMetricsF(p.font())
        bar_w = 96 if self.c.size else 0
        r = plot_rect(QRectF(area.left(), area.top(), area.width() - bar_w, area.height()), fm)
        draw_axes(p, r, self.xa, self.ya)
        p.save()
        p.setClipRect(r)
        px = r.left() + self.xa.map(self.x, r.width())
        py = r.bottom() - self.ya.map(self.y, r.height())
        ok = np.isfinite(px) & np.isfinite(py)
        self._draw_points(p, px, py, ok)
        self._draw_overlay(p, r)
        p.restore()
        p.setPen(BORDER)
        p.drawText(QRectF(r.left() + 6, r.top() + 4, r.width() - 12, fm.height()), Qt.AlignRight,
                   _("{count} points").format(count=int(ok.sum())))
        if self.c.size:
            self._draw_colorbar(p, QRectF(r.right() + 18, r.top(), 16, r.height()), fm)

    def _draw_points(self, p: QPainter, px, py, ok):
        """Points grouped into color levels: one drawPoints call per level instead of one
        drawEllipse per point (higher levels are drawn last, so they end up on top)."""
        pen = QPen(QColor("#2e86c1"), 4.8, Qt.SolidLine, Qt.RoundCap)
        if not self.c.size:
            color = QColor("#2e86c1")
            color.setAlpha(150)
            pen.setColor(color)
            p.setPen(pen)
            p.drawPoints(_points(px[ok], py[ok]))
            return
        lo, hi = self.c_range
        t = (self.c - lo) / (hi - lo) if hi != lo else np.zeros_like(self.c)
        no_color = ok & ~np.isfinite(t)
        pen.setColor(QColor(160, 160, 160, 120))
        p.setPen(pen)
        p.drawPoints(_points(px[no_color], py[no_color]))
        levels = np.clip((np.nan_to_num(t) * (N_LEVELS - 1)).round().astype(int), 0, N_LEVELS - 1)
        palette = colormap(np.linspace(0, 1, N_LEVELS))
        for lvl in range(N_LEVELS):
            sel = ok & np.isfinite(t) & (levels == lvl)
            if sel.any():
                pen.setColor(palette[lvl])
                p.setPen(pen)
                p.drawPoints(_points(px[sel], py[sel]))

    def _draw_overlay(self, p, r):
        if self.overlay == "nd":
            phi = np.linspace(0, 0.4, 41)
            for name, (fn, fr, color) in LITHOLOGY.items():
                xs = r.left() + self.xa.map(fn(phi) * self.neutron_scale, r.width())
                ys = r.bottom() - self.ya.map(fr(phi), r.height())
                p.setPen(QPen(QColor(color), 2))
                for i in range(len(phi) - 1):
                    p.drawLine(QPointF(xs[i], ys[i]), QPointF(xs[i + 1], ys[i + 1]))
                for f in (0.1, 0.2, 0.3):
                    k = int(round(f * 100))
                    p.setBrush(QColor(color))
                    p.drawEllipse(QPointF(xs[k], ys[k]), 3, 3)
                inside = [i for i in range(len(phi)) if r.contains(QPointF(xs[i], ys[i]))]
                if inside:
                    k = inside[int(len(inside) * 0.8)]
                    p.drawText(QPointF(xs[k] + 6, ys[k] + 4), _(name))
            p.setPen(QColor("#566573"))
            p.drawText(QRectF(r.left() + 6, r.bottom() - 20, r.width(), 18), Qt.AlignLeft,
                       _("Approximate lines (limestone neutron); marks every 10 p.u."))
        elif self.overlay == "pickett" and self.pickett:
            pp = self.pickett
            phi = np.logspace(-2, 0, 50)
            for sw, color in ((1.0, "#1a5276"), (0.5, "#27ae60"), (0.25, "#c0392b")):
                rt = pp.a * pp.rw / (phi ** pp.m * sw ** pp.n)
                xs = r.left() + self.xa.map(phi, r.width())
                ys = r.bottom() - self.ya.map(rt, r.height())
                p.setPen(QPen(QColor(color), 1.8, Qt.DashLine))
                valid = np.isfinite(xs) & np.isfinite(ys)
                pts = [QPointF(a, b) for a, b, v in zip(xs, ys, valid) if v]
                for a, b in zip(pts, pts[1:]):
                    p.drawLine(a, b)
                inside = [q for q in pts if r.contains(q)]
                if inside:
                    p.drawText(inside[len(inside) // 2] + QPointF(6, -4), f"Sw={sw:g}")

    def _draw_colorbar(self, p, r, fm):
        n = 60
        for i in range(n):
            col = colormap(np.array([1 - i / (n - 1)]))[0]
            p.fillRect(QRectF(r.left(), r.top() + r.height() * i / n, r.width(), r.height() / n + 1), col)
        p.setPen(BORDER)
        p.setBrush(Qt.NoBrush)
        p.drawRect(r)
        lo, hi = self.c_range
        p.drawText(QRectF(r.right() + 4, r.top(), 60, fm.height()), Qt.AlignLeft | Qt.AlignVCenter, fmt(round(hi, 4)))
        p.drawText(QRectF(r.right() + 4, r.bottom() - fm.height(), 60, fm.height()), Qt.AlignLeft | Qt.AlignVCenter,
                   fmt(round(lo, 4)))
        p.save()
        p.translate(r.right() + 4, r.center().y())
        p.rotate(90)
        p.drawText(QRectF(-r.height() / 2, -fm.height() - 4 - 50, r.height(), fm.height()), Qt.AlignCenter, self.c_label)
        p.restore()


class CrossplotWindow(QDialog):
    def __init__(self, doc: WellDocument, mode: str = "free", parent=None):
        super().__init__(parent)
        self.doc = doc
        w = doc.well
        self.setWindowTitle(_("Crossplot — {well}").format(well=doc.title))
        self.setWindowIcon(app_icon())
        self.setModal(False)
        self.resize(1000, 640)
        lay = QHBoxLayout(self)
        form = QFormLayout()
        self.mode = QComboBox()
        for k, v in (("free", _("Free")), ("nd", _("Neutron - Density")), ("pickett", _("Pickett (φ vs Rt)"))):
            self.mode.addItem(v, k)
        self.x, self.y, self.c = QComboBox(), QComboBox(), QComboBox()
        self.c.addItem(_("(no color)"), None)
        for m in w.curves:
            for combo in (self.x, self.y, self.c):
                combo.addItem(m, m)
        self.logx, self.logy = QCheckBox(_("Logarithmic X")), QCheckBox(_("Logarithmic Y"))
        self.zone = QComboBox()
        for name, top, base in zone_choices(w):
            self.zone.addItem(name, (top, base))
        self.xmin, self.xmax, self.ymin, self.ymax = (QLineEdit() for _i in range(4))
        for e in (self.xmin, self.xmax, self.ymin, self.ymax):
            e.setPlaceholderText("auto")
            e.setMaximumWidth(80)
        pp = doc.petro or PetroParams()
        self.rw = QDoubleSpinBox(decimals=4, minimum=0.001, maximum=100, value=pp.rw, singleStep=0.005)
        self.m = QDoubleSpinBox(decimals=2, minimum=1, maximum=4, value=pp.m, singleStep=0.1)
        self.n = QDoubleSpinBox(decimals=2, minimum=1, maximum=4, value=pp.n, singleStep=0.1)
        self.a = QDoubleSpinBox(decimals=2, minimum=0.1, maximum=5, value=pp.a, singleStep=0.05)
        form.addRow(_("Type:"), self.mode)
        form.addRow(_("X axis:"), self.x)
        form.addRow(_("Y axis:"), self.y)
        form.addRow(_("Color:"), self.c)
        form.addRow(_("Interval:"), self.zone)
        form.addRow(self.logx)
        form.addRow(self.logy)
        form.addRow(_("X min / max:"), self._pair(self.xmin, self.xmax))
        form.addRow(_("Y min / max:"), self._pair(self.ymin, self.ymax))
        self.pickett_label = QLabel(_("<b>Pickett</b> (Sw lines)"))
        form.addRow(self.pickett_label)
        form.addRow("Rw / a:", self._pair(self.rw, self.a))
        form.addRow("m / n:", self._pair(self.m, self.n))
        save = QPushButton(_("Save image…"))
        save.clicked.connect(self._save)
        form.addRow(save)
        side = QWidget()
        side.setLayout(form)
        side.setMaximumWidth(300)
        lay.addWidget(side)
        self.plot = CrossplotWidget()
        lay.addWidget(self.plot, 1)

        self._setting_mode = False
        self.mode.currentIndexChanged.connect(self._mode_changed)
        for wdg in (self.x, self.y, self.c, self.zone):
            wdg.currentIndexChanged.connect(self._update)
        for wdg in (self.logx, self.logy):
            wdg.toggled.connect(self._update)
        for e in (self.xmin, self.xmax, self.ymin, self.ymax):
            e.editingFinished.connect(self._update)
        for s in (self.rw, self.m, self.n, self.a):
            s.valueChanged.connect(self._update)
        self.mode.setCurrentIndex(max(self.mode.findData(mode), 0))
        self._mode_changed()

    @staticmethod
    def _pair(a, b):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(a)
        h.addWidget(b)
        return w

    def _select(self, combo, name):
        if name:
            combo.setCurrentIndex(max(combo.findData(name), 0))

    def _mode_changed(self):
        self._setting_mode = True
        w = self.doc.well
        mode = self.mode.currentData()
        for e in (self.xmin, self.xmax, self.ymin, self.ymax):
            e.clear()
        if mode == "nd":
            self._select(self.x, find_curve(w, "neutron"))
            self._select(self.y, find_curve(w, "density"))
            self._select(self.c, find_curve(w, "gamma_ray"))
            self.logx.setChecked(False)
            self.logy.setChecked(False)
            n = self.x.currentData()
            pct = n is not None and abs(default_scale(w, n)[0]) > 1.5
            k = 100 if pct else 1
            self.xmin.setText(fmt(-0.15 * k))
            self.xmax.setText(fmt(0.45 * k))
            self.ymin.setText("3")
            self.ymax.setText("1.9")
        elif mode == "pickett":
            phi = "PHIE" if "PHIE" in w.curves else find_curve(w, "effective_porosity")
            self._select(self.x, phi)
            self._select(self.y, find_curve(w, "deep_res"))
            self._select(self.c, "VSH" if "VSH" in w.curves else find_curve(w, "gamma_ray"))
            self.logx.setChecked(True)
            self.logy.setChecked(True)
            self.xmin.setText("0.01")
            self.xmax.setText("1")
        for wdg in (self.pickett_label, self.rw, self.a, self.m, self.n):
            wdg.setEnabled(mode == "pickett")
        self._setting_mode = False
        self._update()

    def _axis(self, values, log, lo_edit, hi_edit, label) -> Axis:
        f = values[np.isfinite(values)]
        if log:
            f = f[f > 0]
        if f.size:
            lo, hi = (log_decades if log else nice_linear_range)(float(np.percentile(f, 0.5)), float(np.percentile(f, 99.5)))
        else:
            lo, hi = (0.1, 100) if log else (0, 1)
        try:
            lo = v if (v := parse_float(lo_edit.text())) is not None else lo
            hi = v if (v := parse_float(hi_edit.text())) is not None else hi
        except ValueError:
            pass
        if log and (lo <= 0 or hi <= 0):
            lo, hi = log_decades(lo if lo > 0 else 0.01, hi if hi > 0 else 1)
        if lo == hi:
            hi = lo + 1
        return Axis(lo, hi, log, label)

    def _update(self):
        if self._setting_mode:
            return
        w = self.doc.well
        mx, my, mc = self.x.currentData(), self.y.currentData(), self.c.currentData()
        if not mx or not my:
            return
        top, base = self.zone.currentData()
        mask = w.interval_mask(top, base)
        x, y = w.curves[mx].values[mask], w.curves[my].values[mask]
        c = w.curves[mc].values[mask] if mc else np.array([])
        plot = self.plot
        plot.x, plot.y, plot.c = x, y, c
        unit = lambda m: f" ({w.curves[m].unit})" if w.curves[m].unit else ""  # noqa: E731
        plot.xa = self._axis(x, self.logx.isChecked(), self.xmin, self.xmax, mx + unit(mx))
        plot.ya = self._axis(y, self.logy.isChecked(), self.ymin, self.ymax, my + unit(my))
        if c.size:
            f = c[np.isfinite(c)]
            plot.c_range = (float(np.percentile(f, 2)), float(np.percentile(f, 98))) if f.size else (0.0, 1.0)
            plot.c_label = mc + unit(mc)
        mode = self.mode.currentData()
        plot.overlay = mode if mode in ("nd", "pickett") else None
        plot.neutron_scale = 100 if mode == "nd" and abs(plot.xa.hi) > 1.5 else 1
        plot.pickett = PetroParams(rw=self.rw.value(), a=self.a.value(), m=self.m.value(), n=self.n.value())
        plot.update()

    def _save(self):
        path, _filter = QFileDialog.getSaveFileName(self, _("Save crossplot"), f"{self.doc.title}_crossplot.png",
                                              "PNG (*.png)")
        if path:
            img = QImage(self.plot.size() * 2, QImage.Format_ARGB32)
            img.setDevicePixelRatio(2)
            img.fill(Qt.white)
            p = QPainter(img)
            self.plot.paint_plot(p, QRectF(0, 0, self.plot.width(), self.plot.height()))
            p.end()
            img.save(path)
