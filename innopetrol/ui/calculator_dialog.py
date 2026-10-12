"""Curve calculator: new curves from expressions, evaluated safely (see model.calculator)."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from innopetrol.i18n import _
from innopetrol.model.calculator import FUNCTIONS, CalculatorError, curve_ref, evaluate
from innopetrol.model.well import Curve
from innopetrol.resources import app_icon
from innopetrol.ui.document import WellDocument


class CalculatorDialog(QDialog):
    def __init__(self, doc: WellDocument, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle(_("Curve calculator — {well}").format(well=doc.title))
        self.setWindowIcon(app_icon())
        self.resize(640, 440)
        lay = QHBoxLayout(self)
        left = QVBoxLayout()
        form = QFormLayout()
        self.name = QLineEdit(_("NEW"))
        self.unit = QLineEdit()
        self.descr = QLineEdit()
        form.addRow(_("Name:"), self.name)
        form.addRow(_("Unit:"), self.unit)
        form.addRow(_("Description:"), self.descr)
        left.addLayout(form)
        left.addWidget(QLabel(_("Expression:")))
        self.expr = QPlainTextEdit()
        self.expr.setPlaceholderText(
            _("E.g.: (2.65 - RHOB) / (2.65 - 1.0)") + "\n     where(GR > 75, 1, 0)\n     log10(LLD)"
        )
        left.addWidget(self.expr, 1)
        help_text = "\n".join(
            [
                _("Operators: {operators}").format(operators="+ - * / ** < > <= >= == & |"),
                _("Functions: {functions}").format(functions=", ".join(sorted(FUNCTIONS))),
                _("Constants: pi, e, nan. Curves with special names: [K-3104]"),
                _("DEPTH and TVD: depth of each sample (measured and true vertical, in the file's depth unit)."),
            ]
        )
        hl = QLabel(help_text)
        hl.setWordWrap(True)
        hl.setStyleSheet("color: #566573")
        left.addWidget(hl)
        self.preview = QLabel(" ")
        left.addWidget(self.preview)
        row = QHBoxLayout()
        test = QPushButton(_("Test"))
        test.clicked.connect(self._test)
        row.addWidget(test)
        row.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(_("Create curve"))
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        row.addWidget(buttons)
        left.addLayout(row)
        lay.addLayout(left, 1)

        right = QVBoxLayout()
        right.addWidget(QLabel(_("Curves (double-click to insert):")))
        unit_hint = QLabel(_("Values are used in the file's units, shown in brackets."))
        unit_hint.setWordWrap(True)
        unit_hint.setStyleSheet("color: #566573")
        right.addWidget(unit_hint)
        self.list = QListWidget()
        for m in doc.well.curves:
            unit = doc.well.curves[m].unit
            item = QListWidgetItem(f"{m}  [{unit}]" if unit else m)
            item.setData(Qt.ItemDataRole.UserRole, m)
            self.list.addItem(item)
        self.list.itemDoubleClicked.connect(
            lambda it: self.expr.insertPlainText(curve_ref(it.data(Qt.ItemDataRole.UserRole)))
        )
        right.addWidget(self.list)
        lay.addLayout(right)

    def _evaluate(self) -> np.ndarray | None:
        try:
            return evaluate(self.expr.toPlainText(), self.doc.well.formula_env())
        except CalculatorError as e:
            self.preview.setText("<span style='color:#c0392b'>{}</span>".format(_("Error: {error}").format(error=e)))
            return None

    def _test(self):
        v = self._evaluate()
        if v is not None:
            n = int(np.isfinite(v).sum())
            if n:
                self.preview.setText(
                    _("Valid: {count} samples · min {min} · max {max} · mean {mean}").format(
                        count=n, min=f"{np.nanmin(v):.4g}", max=f"{np.nanmax(v):.4g}", mean=f"{np.nanmean(v):.4g}"
                    )
                )
            else:
                self.preview.setText(_("Valid, but the result has no values (all NaN)"))

    def _ok(self):
        name = self.name.text().strip().upper()
        if not name or not name.replace("_", "").isalnum():
            QMessageBox.warning(self, _("Calculator"), _("Use a name made of letters, digits or _."))
            return
        v = self._evaluate()
        if v is None:
            return
        if name in self.doc.well.curves and self.doc.well.curves[name].formula is None:
            QMessageBox.warning(
                self, _("Calculator"), _("{name} is an original LAS curve; choose another name.").format(name=name)
            )
            return
        formula = " ".join(self.expr.toPlainText().split())
        with self.doc.undo_step(_("Create curve {name}").format(name=name)):
            self.doc.add_curves(
                [
                    Curve(
                        name,
                        self.unit.text().strip(),
                        self.descr.text().strip() or _("Computed curve"),
                        v,
                        formula=formula,
                    )
                ]
            )
        self.accept()
