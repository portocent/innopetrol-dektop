"""Editor of a well's intervals (perforations, tests, losses, cored intervals, runs, comments)."""

from __future__ import annotations

from typing import TypeVar

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
)

from innopetrol.i18n import _
from innopetrol.model.intervals import KINDS, Interval, load_intervals_csv
from innopetrol.resources import app_icon
from innopetrol.ui.document import WellDocument
from innopetrol.ui.widgets import choice_combo, parse_float

T = TypeVar("T")
COL_TOP, COL_BASE, COL_KIND, COL_LABEL = range(4)


class IntervalsDialog(QDialog):
    def __init__(self, doc: WellDocument, parent=None, new: Interval | None = None):
        """`new` (e.g. from the interval selected on the log) is added as an extra row."""
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle(_("Intervals — {well}").format(well=doc.title))
        self.setWindowIcon(app_icon())
        self.resize(640, 460)
        lay = QVBoxLayout(self)
        hint = QLabel(
            _(
                "Measured depths in {unit}. Intervals are drawn in an intervals track (right-click on the log ▸ "
                "Add intervals track); you can also select an interval on the log by dragging."
            ).format(unit=doc.well.depth_unit)
        )
        hint.setWordWrap(True)
        lay.addWidget(hint)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([_("Top"), _("Base"), _("Type"), _("Label")])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(COL_LABEL, QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.table, 1)
        row = QHBoxLayout()
        for text, slot in ((_("Add"), self._add), (_("Remove"), self._remove), (_("Import CSV…"), self._import)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        for interval in doc.well.intervals:
            self._insert(interval)
        if new is not None:
            self._insert(new)
            self.table.setCurrentCell(self.table.rowCount() - 1, COL_LABEL)

    def _insert(self, interval: Interval) -> None:
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setCellWidget(r, COL_TOP, QLineEdit(f"{interval.top:g}"))
        self.table.setCellWidget(r, COL_BASE, QLineEdit(f"{interval.base:g}"))
        self.table.setCellWidget(r, COL_KIND, choice_combo({k: v[0] for k, v in KINDS.items()}, interval.kind))
        self.table.setCellWidget(r, COL_LABEL, QLineEdit(interval.label))

    def _cell(self, row: int, column: int, kind: type[T]) -> T:
        widget = self.table.cellWidget(row, column)
        assert isinstance(widget, kind)
        return widget

    def _add(self) -> None:
        w = self.doc.well
        middle = (w.start + w.stop) / 2
        self._insert(Interval(round(middle, 1), round(middle + 10 * abs(w.step), 1), "comment", ""))

    def _remove(self) -> None:
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    def read(self) -> tuple[list[Interval], list[str]]:
        intervals, errors = [], []
        for r in range(self.table.rowCount()):
            try:
                top = parse_float(self._cell(r, COL_TOP, QLineEdit).text())
                base = parse_float(self._cell(r, COL_BASE, QLineEdit).text())
            except ValueError:
                top = base = None
            if top is None or base is None or top == base:
                errors.append(_("Row {row}: top and base must be different numbers").format(row=r + 1))
                continue
            kind = self._cell(r, COL_KIND, QComboBox).currentData()
            intervals.append(Interval(top, base, kind, self._cell(r, COL_LABEL, QLineEdit).text().strip()))
        return intervals, errors

    def _import(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, _("Import intervals"), "", _("Intervals (*.csv *.txt);;All files (*)")
        )
        if not path:
            return
        try:
            intervals = load_intervals_csv(path)
        except ValueError as e:
            QMessageBox.warning(
                self, _("Import intervals"), _("Could not find top and base columns in: {header}").format(header=e)
            )
            return
        except OSError as e:
            QMessageBox.warning(self, _("Import intervals"), str(e))
            return
        for interval in intervals:
            self._insert(interval)

    def _ok(self) -> None:
        intervals, errors = self.read()
        if errors:
            QMessageBox.warning(self, _("Check the data"), "\n".join(errors))
            return
        self.doc.set_intervals(intervals)
        self.accept()
