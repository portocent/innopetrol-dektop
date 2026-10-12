"""Edición de topes de formación: tabla, importar/exportar CSV."""

from __future__ import annotations

from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget, QVBoxLayout)

from innopetrol.model.tops import PALETTE, Top, load_tops_csv, save_tops_csv
from innopetrol.resources import app_icon
from innopetrol.ui.document import WellDocument
from innopetrol.ui.widgets import ColorButton, parse_float


class TopsDialog(QDialog):
    def __init__(self, doc: WellDocument, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle(f"Topes de formación — {doc.title}")
        self.setWindowIcon(app_icon())
        self.resize(520, 460)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"Profundidades en {doc.well.depth_unit} (rango del registro: "
                             f"{doc.well.start:g} – {doc.well.stop:g}). También puede agregar un tope con clic "
                             "derecho sobre el registro."))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Nombre", "Profundidad", "Color"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        lay.addWidget(self.table, 1)
        row = QHBoxLayout()
        for text, slot in (("Agregar", self._add), ("Quitar", self._remove), ("Importar CSV…", self._import),
                           ("Exportar CSV…", self._export)):
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
        tops, _ = self._read()
        depth = (max((t.depth for t in tops), default=self.doc.well.start) + self.doc.well.stop) / 2
        self._insert(Top(f"Tope {self.table.rowCount() + 1}", round(depth, 1), PALETTE[self.table.rowCount() % len(PALETTE)]))

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
                errors.append(f"Fila {r + 1}: nombre y profundidad numérica son obligatorios")
                continue
            tops.append(Top(name, depth, self.table.cellWidget(r, 2).color()))
        return tops, errors

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importar topes", "", "Topes (*.csv *.txt);;Todos (*)")
        if not path:
            return
        try:
            tops = load_tops_csv(path, well_name=self.doc.well.name)
            if not tops:
                tops = load_tops_csv(path)  # el archivo puede no tener columna de pozo coincidente
        except OSError as e:
            QMessageBox.warning(self, "Importar topes", str(e))
            return
        if not tops:
            QMessageBox.information(self, "Importar topes", "No se encontraron topes en el archivo.\n"
                                    "Formato esperado: nombre, profundidad[, color] (con o sin encabezado).")
            return
        for t in tops:
            self._insert(t)

    def _export(self):
        tops, errors = self._read()
        if errors:
            QMessageBox.warning(self, "Exportar", "\n".join(errors))
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar topes", f"{self.doc.title}_topes.csv", "CSV (*.csv)")
        if path:
            save_tops_csv(path, tops)

    def _ok(self):
        tops, errors = self._read()
        if errors:
            QMessageBox.warning(self, "Revise los datos", "\n".join(errors))
            return
        self.doc.set_tops(tops)
        self.accept()
