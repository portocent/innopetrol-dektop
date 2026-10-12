"""Formation tops editor: table plus CSV import/export."""

from __future__ import annotations

from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget, QVBoxLayout)

from innopetrol.i18n import _
from innopetrol.model.tops import PALETTE, Top, load_tops_csv, save_tops_csv
from innopetrol.resources import app_icon
from innopetrol.ui.document import WellDocument
from innopetrol.ui.widgets import ColorButton, parse_float


class TopsDialog(QDialog):
    def __init__(self, doc: WellDocument, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle(_("Formation tops — {well}").format(well=doc.title))
        self.setWindowIcon(app_icon())
        self.resize(520, 460)
        lay = QVBoxLayout(self)
        hint = QLabel(_("Depths in {unit} (log range: {start} – {stop}). You can also add a top by "
                        "right-clicking on the log.").format(unit=doc.well.depth_unit, start=f"{doc.well.start:g}",
                                                             stop=f"{doc.well.stop:g}"))
        hint.setWordWrap(True)
        lay.addWidget(hint)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels([_("Name"), _("Depth"), _("Color")])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        lay.addWidget(self.table, 1)
        row = QHBoxLayout()
        for text, slot in ((_("Add"), self._add), (_("Remove"), self._remove), (_("Import CSV…"), self._import),
                           (_("Export CSV…"), self._export)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            row.addWidget(b)
        lay.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        for t in doc.well.tops:
            self._insert(t)

    def _insert(self, t: Top):
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setCellWidget(r, 0, QLineEdit(t.name))
        self.table.setCellWidget(r, 1, QLineEdit(f"{t.depth:g}"))
        self.table.setCellWidget(r, 2, ColorButton(t.color))

    def _add(self):
        tops, _errors = self._read()
        depth = (max((t.depth for t in tops), default=self.doc.well.start) + self.doc.well.stop) / 2
        self._insert(Top(_("Top {number}").format(number=self.table.rowCount() + 1), round(depth, 1), PALETTE[self.table.rowCount() % len(PALETTE)]))

    def _remove(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    def _read(self) -> tuple[list[Top], list[str]]:
        tops, errors = [], []
        for r in range(self.table.rowCount()):
            name = self.table.cellWidget(r, 0).text().strip()
            try:
                depth = parse_float(self.table.cellWidget(r, 1).text())
            except ValueError:
                depth = None
            if not name or depth is None:
                errors.append(_("Row {row}: a name and a numeric depth are required").format(row=r + 1))
                continue
            tops.append(Top(name, depth, self.table.cellWidget(r, 2).color()))
        return tops, errors

    def _import(self):
        path, _filter = QFileDialog.getOpenFileName(self, _("Import tops"), "",
                                                     _("Tops (*.csv *.txt);;All files (*)"))
        if not path:
            return
        try:
            tops = load_tops_csv(path, well_name=self.doc.well.name)
            if not tops:
                tops = load_tops_csv(path)  # the file may not have a matching well column
        except OSError as e:
            QMessageBox.warning(self, _("Import tops"), str(e))
            return
        if not tops:
            QMessageBox.information(self, _("Import tops"), _("No tops were found in the file.\n"
                                    "Expected format: name, depth[, color] (with or without a header)."))
            return
        for t in tops:
            self._insert(t)

    def _export(self):
        tops, errors = self._read()
        if errors:
            QMessageBox.warning(self, _("Export"), "\n".join(errors))
            return
        path, _filter = QFileDialog.getSaveFileName(self, _("Export tops"), f"{self.doc.title}_tops.csv",
                                                     "CSV (*.csv)")
        if path:
            save_tops_csv(path, tops)

    def _ok(self):
        tops, errors = self._read()
        if errors:
            QMessageBox.warning(self, _("Check the data"), "\n".join(errors))
            return
        self.doc.set_tops(tops)
        self.accept()
