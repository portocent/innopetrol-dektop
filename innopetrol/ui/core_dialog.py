"""Import core (laboratory) data from CSV as point curves on the log."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from innopetrol.i18n import _
from innopetrol.model.core import CoreTable, core_curve, core_mnemonic
from innopetrol.model.layout import TrackSpec
from innopetrol.model.scales import MM_PER_UNIT
from innopetrol.resources import app_icon
from innopetrol.ui.document import WellDocument
from innopetrol.ui.widgets import spin

COL_NAME, COL_CURVE, COL_UNIT = range(3)
NEW_TRACK = -1
COLORS = ["#d35400", "#8e44ad", "#16a085", "#2c3e50", "#c0392b", "#2980b9"]


class CoreDialog(QDialog):
    def __init__(self, doc: WellDocument, table: CoreTable, source: str, parent=None):
        super().__init__(parent)
        self.doc, self.data = doc, table
        self.setWindowTitle(_("Import core data — {well}").format(well=doc.title))
        self.setWindowIcon(app_icon())
        self.resize(620, 480)
        lay = QVBoxLayout(self)
        info = QLabel(
            _("{file}: {count} samples between {top} and {base}. Check the columns to import.").format(
                file=Path(source).name,
                count=table.depths.size,
                top=f"{np.nanmin(table.depths):g}",
                base=f"{np.nanmax(table.depths):g}",
            )
        )
        info.setWordWrap(True)
        lay.addWidget(info)
        self.table = QTableWidget(len(table.columns), 3)
        self.table.setHorizontalHeaderLabels([_("Column"), _("Curve"), _("Unit")])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for r, (name, (unit, _values)) in enumerate(table.columns.items()):
            check = QTableWidgetItem(name)
            check.setFlags(check.flags() & ~Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsUserCheckable)
            check.setCheckState(Qt.CheckState.Checked)
            self.table.setItem(r, COL_NAME, check)
            self.table.setItem(r, COL_CURVE, QTableWidgetItem(core_mnemonic(name)))
            self.table.setItem(r, COL_UNIT, QTableWidgetItem(unit))
        lay.addWidget(self.table, 1)
        form = QFormLayout()
        self.depth_unit = QComboBox()
        for unit in ("m", "ft"):
            self.depth_unit.addItem(unit, unit)
        self.depth_unit.setCurrentIndex(max(self.depth_unit.findData(doc.well.depth_unit), 0))
        self.shift = spin(0.0, -1000, 1000, 0.1, 2)
        self.track = QComboBox()
        self.track.addItem(_("A new “Core” track"), NEW_TRACK)
        for i, t in enumerate(doc.layout.tracks):
            if not t.is_depth:
                self.track.addItem(t.title or _("Track {number}").format(number=i + 1), i)
        form.addRow(_("Core depths in:"), self.depth_unit)
        form.addRow(_("Core-to-log depth shift (added):"), self.shift)
        form.addRow(_("Show in:"), self.track)
        lay.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(_("Import"))
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def depths(self) -> np.ndarray:
        """Core depths in the well's unit and shifted to the log."""
        factor = MM_PER_UNIT[self.depth_unit.currentData()] / MM_PER_UNIT[self.doc.well.depth_unit]
        return self.data.depths * factor + self.shift.value()

    def _item(self, row: int, column: int) -> QTableWidgetItem:
        item = self.table.item(row, column)
        assert item is not None  # every cell is created with the table
        return item

    def _ok(self) -> None:
        curves = []
        names = list(self.data.columns)
        for r, column in enumerate(names):
            if self._item(r, COL_NAME).checkState() != Qt.CheckState.Checked:
                continue
            mnemonic = self._item(r, COL_CURVE).text().strip().upper()
            existing = self.doc.well.curves.get(mnemonic)
            if not mnemonic or (existing is not None and existing.points is None):
                QMessageBox.warning(
                    self,
                    self.windowTitle(),
                    _("{name} already exists in the well; choose another name.").format(name=mnemonic or "—"),
                )
                return
            values = self.data.columns[column][1]
            description = _("Core: {column}").format(column=column)
            curves.append(
                core_curve(
                    self.doc.well, mnemonic, self._item(r, COL_UNIT).text().strip(), description, self.depths(), values
                )
            )
        placed = [c for c in curves if np.isfinite(c.values).any()]
        if not placed:
            QMessageBox.warning(self, self.windowTitle(), _("No core sample falls inside the logged interval."))
            return
        with self.doc.undo_step(_("Import core data")):
            self.doc.add_curves(placed)
            self._show(placed)
        self.accept()

    def _show(self, curves) -> None:
        target = self.track.currentData()
        if target == NEW_TRACK:
            track = TrackSpec(title=_("Core"), width=170)
            self.doc.layout.tracks.append(track)
        else:
            track = self.doc.layout.tracks[target]
        for i, curve in enumerate(curves):
            style = self.doc.style_for(curve.mnemonic)
            style.color, style.width = COLORS[i % len(COLORS)], 2.0
            track.curves.append(style)
        self.doc.layoutChanged.emit()
