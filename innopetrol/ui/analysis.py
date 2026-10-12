"""Statistics with a histogram, and a data table synchronized with the cursor."""

from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QSpinBox, QTableView,
                               QVBoxLayout, QWidget)

from innopetrol.i18n import _
from innopetrol.model.scales import log_decades, nice_linear_range
from innopetrol.model.tops import zones_from_tops
from innopetrol.resources import app_icon
from innopetrol.ui.document import WellDocument
from innopetrol.ui.plotting import Axis, draw_axes, plot_rect


def zone_choices(well) -> list[tuple[str, float | None, float | None]]:
    out = [(_("Whole well"), None, None)]
    for z in zones_from_tops(well.tops, well.stop):
        out.append((f"{z.name} ({z.top:g}–{z.base:g})", z.top, z.base))
    return out


# ============================================================================ histogram


class Histogram(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.values = np.array([])
        self.log = False
        self.bins = 40
        self.label = ""
        self.color = QColor("#2e86c1")
        self.setMinimumSize(420, 280)

    def set_data(self, values: np.ndarray, label: str, log: bool, bins: int, color: str):
        self.values = values[np.isfinite(values)]
        if log:
            self.values = self.values[self.values > 0]
        self.label, self.log, self.bins, self.color = label, log, bins, QColor(color)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#f7f8f9"))
        fm = QFontMetricsF(self.font())
        r = plot_rect(QRectF(self.rect()), fm)
        if self.values.size == 0:
            p.drawText(self.rect(), Qt.AlignCenter, _("No data in the interval"))
            p.end()
            return
        lo, hi = (log_decades if self.log else nice_linear_range)(float(self.values.min()), float(self.values.max()))
        edges = np.logspace(np.log10(lo), np.log10(hi), self.bins + 1) if self.log else np.linspace(lo, hi, self.bins + 1)
        counts, _edges = np.histogram(self.values, edges)
        freq = counts / counts.sum() * 100
        ymax = max(float(freq.max()) * 1.1, 1)
        xa = Axis(lo, hi, self.log, self.label)
        ya = Axis(0, ymax, False, _("Frequency (%)"))
        draw_axes(p, r, xa, ya)
        xs = r.left() + xa.map(edges, r.width())
        p.setPen(QPen(self.color.darker(130), 0.8))
        p.setBrush(self.color)
        for i, f in enumerate(freq):
            h = f / ymax * r.height()
            p.drawRect(QRectF(xs[i], r.bottom() - h, xs[i + 1] - xs[i], h))
        # Cumulative curve
        cum = np.cumsum(freq) / 100 * r.height()
        p.setPen(QPen(QColor("#c0392b"), 1.5))
        pts = [(xs[i + 1], r.bottom() - c) for i, c in enumerate(cum)]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            p.drawLine(int(x0), int(y0), int(x1), int(y1))
        p.end()


class StatsDialog(QDialog):
    def __init__(self, doc: WellDocument, curve: str | None = None, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle(_("Statistics — {well}").format(well=doc.title))
        self.setWindowIcon(app_icon())
        self.resize(820, 460)
        lay = QHBoxLayout(self)
        side = QFormLayout()
        self.curve = QComboBox()
        for m in doc.well.curves:
            self.curve.addItem(m, m)
        if curve:
            self.curve.setCurrentIndex(max(self.curve.findData(curve), 0))
        self.zone = QComboBox()
        for name, top, base in zone_choices(doc.well):
            self.zone.addItem(name, (top, base))
        self.log = QCheckBox(_("Logarithmic scale"))
        self.bins = QSpinBox()
        self.bins.setRange(5, 200)
        self.bins.setValue(40)
        self.stats = QLabel()
        self.stats.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.stats.setAlignment(Qt.AlignTop)
        side.addRow(_("Curve:"), self.curve)
        side.addRow(_("Interval:"), self.zone)
        side.addRow(_("Bins:"), self.bins)
        side.addRow(self.log)
        side.addRow(self.stats)
        box = QWidget()
        box.setLayout(side)
        box.setMaximumWidth(300)
        lay.addWidget(box)
        self.hist = Histogram()
        lay.addWidget(self.hist, 1)
        for w in (self.curve, self.zone):
            w.currentIndexChanged.connect(self._update)
        self.log.toggled.connect(self._update)
        self.bins.valueChanged.connect(self._update)
        self._initial_log()
        self._update()

    def _initial_log(self):
        m = self.curve.currentData()
        for t in self.doc.layout.tracks:
            for c in t.curves:
                if c.mnemonic == m:
                    self.log.setChecked(c.log)
                    return

    def _update(self):
        m = self.curve.currentData()
        if not m:
            return
        top, base = self.zone.currentData()
        curve = self.doc.well.curves[m]
        v = curve.values[self.doc.well.interval_mask(top, base)]
        f = v[np.isfinite(v)]
        if f.size:
            p10, p50, p90 = np.percentile(f, [10, 50, 90])
            lines = [
                _("Valid samples: {valid} of {total}").format(valid=f.size, total=v.size),
                _("Minimum: {value}").format(value=f"{f.min():.4g}"),
                _("Maximum: {value}").format(value=f"{f.max():.4g}"),
                _("Mean: {value}").format(value=f"{f.mean():.4g}"),
                _("Std. deviation: {value}").format(value=f"{f.std():.4g}"),
                f"P10: {p10:.4g}",
                _("P50 (median): {value}").format(value=f"{p50:.4g}"),
                f"P90: {p90:.4g}",
            ]
            txt = f"<b>{m}</b> {curve.unit}<br>{curve.description}<br><br>" + "<br>".join(lines)
            if curve.formula:
                txt += "<br><br><i>{}</i> {}".format(_("Formula:"), curve.formula)
        else:
            txt = f"<b>{m}</b>: " + _("no data in the interval")
        self.stats.setText(txt)
        color = next((c.color for t in self.doc.layout.tracks for c in t.curves if c.mnemonic == m), "#2e86c1")
        self.hist.set_data(v, f"{m} ({curve.unit})" if curve.unit else m, self.log.isChecked(),
                           self.bins.value(), color)


# ============================================================================ data table


class CurveTableModel(QAbstractTableModel):
    """Depth columns (MD, plus TVD/TVDSS when a survey or elevation exists) followed by every curve."""

    def __init__(self, well, parent=None):
        super().__init__(parent)
        self.well = well
        self._build()

    def _build(self):
        w = self.well
        self.depths = [(f"{w.depth_mnemonic}\n{w.depth_unit}", w.depth)]
        if w.survey is not None or w.elevation is not None:
            tvd = w.tvd()
            if w.survey is not None:
                self.depths.append((f"TVD\n{w.depth_unit}", tvd))
            if w.elevation is not None:
                self.depths.append((f"TVDSS\n{w.depth_unit}", tvd - w.elevation))
        self.names = list(w.curves)

    def refresh(self):
        self.beginResetModel()
        self._build()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else self.well.depth.size

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.names) + len(self.depths)

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            r, c = index.row(), index.column()
            nd = len(self.depths)
            v = self.depths[c][1][r] if c < nd else self.well.curves[self.names[c - nd]].values[r]
            return "" if not np.isfinite(v) else f"{v:.4f}".rstrip("0").rstrip(".")
        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            if section < len(self.depths):
                return self.depths[section][0]
            c = self.well.curves[self.names[section - len(self.depths)]]
            return f"{c.mnemonic}\n{c.unit}"
        return str(section + 1)


class DataTableWindow(QDialog):
    """Non-modal window: moving the cursor over the log scrolls the table to that depth, and
    selecting a row marks that depth on the log."""

    def __init__(self, doc: WellDocument, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle(_("Data — {well}").format(well=doc.title))
        self.setWindowIcon(app_icon())
        self.resize(760, 560)
        self.setModal(False)
        lay = QVBoxLayout(self)
        self.follow = QCheckBox(_("Follow the log cursor"))
        self.follow.setChecked(True)
        lay.addWidget(self.follow)
        self.model = CurveTableModel(doc.well, self)
        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.setSelectionBehavior(QTableView.SelectRows)
        self.view.verticalHeader().setDefaultSectionSize(20)
        lay.addWidget(self.view)
        doc.cursorMoved.connect(self._follow)
        doc.curvesChanged.connect(self.model.refresh)
        doc.layoutChanged.connect(self.model.refresh)  # survey or elevation changed
        self.view.selectionModel().currentRowChanged.connect(self._row_changed)
        self._internal = False

    def _follow(self, depth: float):
        if self._internal or not self.follow.isChecked() or math.isnan(depth):
            return
        r = int(np.clip(np.searchsorted(self.doc.well.depth, depth), 0, self.doc.well.depth.size - 1))
        self._internal = True
        self.view.selectRow(r)
        self.view.scrollTo(self.model.index(r, 0), QTableView.PositionAtCenter)
        self._internal = False

    def _row_changed(self, current, _previous):
        if not self._internal and current.isValid():
            self._internal = True
            self.doc.cursorMoved.emit(float(self.doc.well.depth[current.row()]))
            self._internal = False
