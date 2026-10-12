"""Statistics with a histogram, and a data table synchronized with the cursor."""

from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QSpinBox, QTableView,
                               QVBoxLayout, QWidget)

from innopetrol.i18n import _
from innopetrol.model.scales import log_decades, nice_linear_range
from innopetrol.model.tops import zones_from_tops
from innopetrol.resources import app_icon
from innopetrol.ui.document import WellDocument
from innopetrol.ui.multiwell import checked_docs, color_of, values_as, well_list, zone_mask, zone_names
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
        self.series: list[tuple[np.ndarray, QColor, str]] = []
        self.log = False
        self.bins = 40
        self.label = ""
        self.color = QColor("#2e86c1")
        self.setMinimumSize(420, 280)

    def set_data(self, values: np.ndarray, label: str, log: bool, bins: int, color: str):
        self.set_series([(values, color, "")], label, log, bins)

    def set_series(self, series: list[tuple[np.ndarray, str, str]], label: str, log: bool, bins: int):
        """One or more (values, color, name). Several are drawn as outlines so they can be compared."""
        clean = []
        for values, color, name in series:
            v = values[np.isfinite(values)]
            if log:
                v = v[v > 0]
            clean.append((v, QColor(color), name))
        self.series = clean
        self.values = np.concatenate([v for v, _color, _name in clean]) if clean else np.array([])
        self.label, self.log, self.bins = label, log, bins
        self.color = clean[0][1] if clean else QColor("#2e86c1")
        self.update()

    @property
    def plot_area(self) -> QRectF:
        return plot_rect(QRectF(self.rect()), QFontMetricsF(self.font()))

    @property
    def x_axis(self) -> Axis | None:
        if self.values.size == 0:
            return None
        lo, hi = (log_decades if self.log else nice_linear_range)(float(self.values.min()), float(self.values.max()))
        return Axis(lo, hi, self.log, self.label)

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#f7f8f9"))
        r = self.plot_area
        if self.values.size == 0:
            p.drawText(self.rect(), Qt.AlignCenter, _("No data in the interval"))
            p.end()
            return
        xa = self.x_axis
        lo, hi = xa.lo, xa.hi
        edges = np.logspace(np.log10(lo), np.log10(hi), self.bins + 1) if self.log else np.linspace(lo, hi, self.bins + 1)
        if len(self.series) > 1:
            self._paint_outlines(p, r, xa, edges)
            p.end()
            return
        counts, _edges = np.histogram(self.values, edges)
        freq = counts / counts.sum() * 100
        ymax = max(float(freq.max()) * 1.1, 1)
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
        self.paint_overlay(p, r, xa)
        p.end()

    def _paint_outlines(self, p: QPainter, r: QRectF, xa: Axis, edges: np.ndarray) -> None:
        """Several wells: each histogram as a stepped outline, normalized to its own sample count."""
        freqs = []
        for v, _color, _name in self.series:
            counts, _edges = np.histogram(v, edges)
            freqs.append(counts / counts.sum() * 100 if counts.sum() else counts.astype(float))
        ymax = max(max((float(f.max()) for f in freqs), default=1) * 1.1, 1)
        draw_axes(p, r, xa, Axis(0, ymax, False, _("Frequency (%)")))
        xs = r.left() + xa.map(edges, r.width())
        p.setRenderHint(QPainter.Antialiasing)
        fm = QFontMetricsF(self.font())
        for i, ((_v, color, name), f) in enumerate(zip(self.series, freqs)):
            ys = r.bottom() - f / ymax * r.height()
            path = [QPointF(xs[0], r.bottom())]
            for k, y in enumerate(ys):
                path += [QPointF(xs[k], y), QPointF(xs[k + 1], y)]
            path.append(QPointF(xs[-1], r.bottom()))
            p.setPen(QPen(color, 2))
            p.drawPolyline(path)
            ly = r.top() + 6 + i * (fm.height() + 2)
            p.drawLine(QPointF(r.right() - 150, ly + fm.height() / 2), QPointF(r.right() - 130, ly + fm.height() / 2))
            p.setPen(QColor("#2c3e50"))
            p.drawText(QRectF(r.right() - 125, ly, 120, fm.height()), Qt.AlignLeft | Qt.AlignVCenter,
                       fm.elidedText(name, Qt.ElideRight, 120))

    def paint_overlay(self, p: QPainter, r: QRectF, xa: Axis) -> None:
        """Hook for subclasses that draw on top of the histogram (e.g. parameter picking lines)."""


class StatsDialog(QDialog):
    def __init__(self, doc: WellDocument, curve: str | None = None, parent=None, docs: list | None = None):
        super().__init__(parent)
        self.doc = doc
        self.docs = list(docs or [doc])
        if doc not in self.docs:
            self.docs.insert(0, doc)
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
        self.wells = well_list(self.docs, doc) if len(self.docs) > 1 else None
        self.zone = QComboBox()
        self._fill_zones()
        self.log = QCheckBox(_("Logarithmic scale"))
        self.bins = QSpinBox()
        self.bins.setRange(5, 200)
        self.bins.setValue(40)
        self.stats = QLabel()
        self.stats.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.stats.setAlignment(Qt.AlignTop)
        side.addRow(_("Curve:"), self.curve)
        if self.wells is not None:
            side.addRow(_("Wells:"), self.wells)
            self.wells.itemChanged.connect(self._wells_changed)
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

    def _fill_zones(self):
        current = self.zone.currentData()
        docs = checked_docs(self.wells) if self.wells is not None else [self.doc]
        self.zone.blockSignals(True)
        self.zone.clear()
        self.zone.addItem(_("Whole well"), None)
        for name in zone_names(docs):
            self.zone.addItem(name, name)
        self.zone.setCurrentIndex(max(self.zone.findData(current), 0))
        self.zone.blockSignals(False)

    def _wells_changed(self):
        self._fill_zones()
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
        zone = self.zone.currentData()
        curve = self.doc.view.curves[m]  # as displayed (unit chosen by the user)
        docs = checked_docs(self.wells) if self.wells is not None else [self.doc]
        if len(docs) > 1:
            self._update_wells(m, curve, zone, docs)
            return
        v = curve.values[zone_mask(self.doc, zone)]
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

    def _update_wells(self, m, curve, zone, docs):
        """Several wells: one outline per well and a comparison table of P10/P50/P90."""
        series, rows = [], []
        for d in docs:
            values = values_as(d, m, self.doc)
            if values is None:
                rows.append(f"<tr><td>{d.title}</td><td colspan=4>{_('no equivalent curve')}</td></tr>")
                continue
            v = values[zone_mask(d, zone)]
            f = v[np.isfinite(v)]
            series.append((v, color_of(self.wells, d), d.title))
            if f.size:
                p10, p50, p90 = np.percentile(f, [10, 50, 90])
                rows.append(f"<tr><td>{d.title}</td><td>{f.size}</td><td>{p10:.4g}</td><td>{p50:.4g}</td>"
                            f"<td>{p90:.4g}</td></tr>")
            else:
                rows.append(f"<tr><td>{d.title}</td><td colspan=4>{_('no data in the interval')}</td></tr>")
        head = "<tr><th align=left>{}</th><th>n</th><th>P10</th><th>P50</th><th>P90</th></tr>".format(_("Well"))
        self.stats.setText(f"<b>{m}</b> {curve.unit}<br><br><table cellspacing=4>{head}{''.join(rows)}</table>")
        self.hist.set_series(series, f"{m} ({curve.unit})" if curve.unit else m, self.log.isChecked(),
                             self.bins.value())


# ============================================================================ data table


class CurveTableModel(QAbstractTableModel):
    """Depth columns (MD, plus TVD/TVDSS when a survey or elevation exists) followed by every curve."""

    def __init__(self, doc, parent=None):
        super().__init__(parent)
        self.doc = doc
        self._build()

    @property
    def well(self):
        return self.doc.well

    def _build(self):
        w = self.well
        self.curves = self.doc.view.curves  # values and units as displayed
        self.depths = [(f"{w.depth_mnemonic}\n{w.depth_unit}", w.depth)]
        if w.survey is not None or w.elevation is not None:
            tvd = w.tvd()
            if w.survey is not None:
                self.depths.append((f"TVD\n{w.depth_unit}", tvd))
            if w.elevation is not None:
                self.depths.append((f"TVDSS\n{w.depth_unit}", tvd - w.elevation))
        self.names = list(self.curves)

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
            v = self.depths[c][1][r] if c < nd else self.curves[self.names[c - nd]].values[r]
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
            c = self.curves[self.names[section - len(self.depths)]]
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
        self.model = CurveTableModel(doc, self)
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
