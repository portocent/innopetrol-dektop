"""Estadísticas con histograma y tabla de datos sincronizada con el cursor."""

from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QSpinBox, QTableView,
                               QVBoxLayout, QWidget)

from innopetrol.model.scales import log_decades, nice_linear_range
from innopetrol.model.tops import zones_from_tops
from innopetrol.resources import app_icon
from innopetrol.ui.document import WellDocument
from innopetrol.ui.plotting import Axis, draw_axes, plot_rect


def zone_choices(well) -> list[tuple[str, float | None, float | None]]:
    out = [("Pozo completo", None, None)]
    for z in zones_from_tops(well.tops, well.stop):
        out.append((f"{z.name} ({z.top:g}–{z.base:g})", z.top, z.base))
    return out


# ============================================================================ histograma


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
            p.drawText(self.rect(), Qt.AlignCenter, "Sin datos en el intervalo")
            p.end()
            return
        lo, hi = (log_decades if self.log else nice_linear_range)(float(self.values.min()), float(self.values.max()))
        edges = np.logspace(np.log10(lo), np.log10(hi), self.bins + 1) if self.log else np.linspace(lo, hi, self.bins + 1)
        counts, _ = np.histogram(self.values, edges)
        freq = counts / counts.sum() * 100
        ymax = max(float(freq.max()) * 1.1, 1)
        xa = Axis(lo, hi, self.log, self.label)
        ya = Axis(0, ymax, False, "Frecuencia (%)")
        draw_axes(p, r, xa, ya)
        xs = r.left() + xa.map(edges, r.width())
        p.setPen(QPen(self.color.darker(130), 0.8))
        p.setBrush(self.color)
        for i, f in enumerate(freq):
            h = f / ymax * r.height()
            p.drawRect(QRectF(xs[i], r.bottom() - h, xs[i + 1] - xs[i], h))
        # Curva acumulada
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
        self.setWindowTitle(f"Estadísticas — {doc.title}")
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
        self.log = QCheckBox("Escala logarítmica")
        self.bins = QSpinBox()
        self.bins.setRange(5, 200)
        self.bins.setValue(40)
        self.stats = QLabel()
        self.stats.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.stats.setAlignment(Qt.AlignTop)
        side.addRow("Curva:", self.curve)
        side.addRow("Intervalo:", self.zone)
        side.addRow("Clases:", self.bins)
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
            txt = (f"<b>{m}</b> {curve.unit}<br>{curve.description}<br><br>"
                   f"Muestras válidas: {f.size} de {v.size}<br>"
                   f"Mínimo: {f.min():.4g}<br>Máximo: {f.max():.4g}<br>Media: {f.mean():.4g}<br>"
                   f"Desv. estándar: {f.std():.4g}<br>P10: {p10:.4g}<br>P50 (mediana): {p50:.4g}<br>P90: {p90:.4g}")
            if curve.formula:
                txt += f"<br><br><i>Fórmula:</i> {curve.formula}"
        else:
            txt = f"<b>{m}</b>: sin datos en el intervalo"
        self.stats.setText(txt)
        color = next((c.color for t in self.doc.layout.tracks for c in t.curves if c.mnemonic == m), "#2e86c1")
        self.hist.set_data(v, f"{m} ({curve.unit})" if curve.unit else m, self.log.isChecked(),
                           self.bins.value(), color)


# ============================================================================ tabla de datos


class CurveTableModel(QAbstractTableModel):
    def __init__(self, well, parent=None):
        super().__init__(parent)
        self.well = well
        self.names = list(well.curves)

    def refresh(self):
        self.beginResetModel()
        self.names = list(self.well.curves)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else self.well.depth.size

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.names) + 1

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            r, c = index.row(), index.column()
            v = self.well.depth[r] if c == 0 else self.well.curves[self.names[c - 1]].values[r]
            return "" if not np.isfinite(v) else f"{v:.4f}".rstrip("0").rstrip(".")
        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            if section == 0:
                return f"{self.well.depth_mnemonic}\n{self.well.depth_unit}"
            c = self.well.curves[self.names[section - 1]]
            return f"{c.mnemonic}\n{c.unit}"
        return str(section + 1)


class DataTableWindow(QDialog):
    """Ventana no modal: al mover el cursor sobre el registro, la tabla salta a esa profundidad
    y al seleccionar una fila se marca esa profundidad en el registro."""

    def __init__(self, doc: WellDocument, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle(f"Datos — {doc.title}")
        self.setWindowIcon(app_icon())
        self.resize(760, 560)
        self.setModal(False)
        lay = QVBoxLayout(self)
        self.follow = QCheckBox("Seguir el cursor del registro")
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
