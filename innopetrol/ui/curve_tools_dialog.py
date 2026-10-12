"""Curve editing: depth shift, smoothing, running median and despiking.

The result is a new computed curve whose formula records the operation (e.g. `despike(GR, 7, 3)`),
so the original data is never changed and the edit is undoable and recomputed with the project.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from innopetrol.i18n import N_, _
from innopetrol.model.calculator import CalculatorError, curve_ref, evaluate
from innopetrol.model.layout import CurveStyle
from innopetrol.model.well import Curve
from innopetrol.resources import app_icon
from innopetrol.ui.document import WellDocument
from innopetrol.ui.widgets import choice_combo, curve_combo, spin

# operation -> (display name, suffix of the new curve)
OPERATIONS = {
    "shift": (N_("Depth shift"), "SH"),
    "despike": (N_("Remove spikes (despike)"), "DS"),
    "median": (N_("Running median"), "MED"),
    "smooth": (N_("Smoothing (moving average)"), "SM"),
}


class CurveToolsDialog(QDialog):
    def __init__(self, doc: WellDocument, curve: str | None = None, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle(_("Edit curve — {well}").format(well=doc.title))
        self.setWindowIcon(app_icon())
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.curve = curve_combo(doc.well, curve, optional=False)
        self.operation = choice_combo({k: v[0] for k, v in OPERATIONS.items()}, "despike")
        form.addRow(_("Curve:"), self.curve)
        form.addRow(_("Operation:"), self.operation)
        lay.addLayout(form)
        self.pages = QStackedWidget()
        self.pages.addWidget(self._shift_page())
        self.pages.addWidget(self._window_page(with_threshold=True))
        self.pages.addWidget(self._window_page(with_threshold=False))
        self.pages.addWidget(self._window_page(with_threshold=False))
        lay.addWidget(self.pages)
        out = QFormLayout()
        self.name = QLineEdit()
        self.show_in_track = QCheckBox(_("Show it, dashed, in the tracks of the original curve"))
        self.show_in_track.setChecked(True)
        out.addRow(_("New curve:"), self.name)
        out.addRow(self.show_in_track)
        lay.addLayout(out)
        self.preview = QLabel(" ")
        self.preview.setWordWrap(True)
        self.preview.setStyleSheet("color:#566573")
        lay.addWidget(self.preview)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(_("Create curve"))
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        for signal in (self.curve.currentIndexChanged, self.operation.currentIndexChanged):
            signal.connect(self._changed)
        self.offset.valueChanged.connect(self._update_preview)
        self.threshold.valueChanged.connect(self._update_preview)
        for window in self.windows:
            window.valueChanged.connect(self._update_preview)
        self._changed()

    # ---------------------------------------------------------------- construction
    def _shift_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.offset = spin(0.0, -1000, 1000, 0.1, 2)
        self.offset.setSuffix(f" {self.doc.well.depth_unit}")
        form.addRow(_("Move deeper by (negative: shallower):"), self.offset)
        self.windows: list[QSpinBox] = []
        return page

    def _window_page(self, with_threshold: bool) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        window = QSpinBox()
        window.setRange(3, 501)
        window.setSingleStep(2)
        window.setValue(7 if with_threshold else 5)
        self.windows.append(window)
        step = self.doc.well.step
        form.addRow(_("Window (samples, odd):"), window)
        form.addRow(
            QLabel(_("One sample = {step} {unit}").format(step=f"{abs(step):g}", unit=self.doc.well.depth_unit))
        )
        if with_threshold:
            self.threshold = QDoubleSpinBox(decimals=1, minimum=0.5, maximum=20, value=3.0, singleStep=0.5)
            form.addRow(_("Threshold (robust standard deviations):"), self.threshold)
        return page

    # ---------------------------------------------------------------- formula
    def formula(self) -> str:
        ref = curve_ref(self.curve.currentData())
        op = self.operation.currentData()
        if op == "shift":
            return f"shift({ref}, DEPTH, {self.offset.value():g})"
        window = self.windows[list(OPERATIONS).index(op) - 1].value()
        if op == "despike":
            return f"despike({ref}, {window}, {self.threshold.value():g})"
        return f"{op}({ref}, {window})"

    def _changed(self):
        op = self.operation.currentData()
        self.pages.setCurrentIndex(list(OPERATIONS).index(op))
        self.name.setText(f"{self.curve.currentData()}_{OPERATIONS[op][1]}")
        self._update_preview()

    def _evaluate(self) -> np.ndarray | None:
        try:
            return evaluate(self.formula(), self.doc.well.formula_env())
        except CalculatorError as e:
            self.preview.setText(_("Error: {error}").format(error=e))
            return None

    def _update_preview(self):
        values = self._evaluate()
        if values is None:
            return
        original = self.doc.well.curves[self.curve.currentData()].values
        with np.errstate(invalid="ignore"):
            changed = int(np.sum(np.isfinite(values) & np.isfinite(original) & ~np.isclose(values, original)))
        self.preview.setText(
            f"= {self.formula()}\n"
            + _("{changed} of {total} samples change.").format(changed=changed, total=int(np.isfinite(original).sum()))
        )

    def _ok(self):
        name = self.name.text().strip().upper()
        if not name or not name.replace("_", "").isalnum():
            QMessageBox.warning(self, self.windowTitle(), _("Use a name made of letters, digits or _."))
            return
        if name in self.doc.well.curves and self.doc.well.curves[name].formula is None:
            QMessageBox.warning(
                self, self.windowTitle(), _("{name} is an original LAS curve; choose another name.").format(name=name)
            )
            return
        values = self._evaluate()
        if values is None:
            return
        source = self.doc.well.curves[self.curve.currentData()]
        description = f"{_(OPERATIONS[self.operation.currentData()][0])}: {source.mnemonic}"
        with self.doc.undo_step(_("Create curve {name}").format(name=name)):
            self.doc.add_curves([Curve(name, source.unit, description, values, formula=self.formula())])
            if self.show_in_track.isChecked():
                self._show_next_to(source.mnemonic, name)
        self.accept()

    def _show_next_to(self, original: str, name: str) -> None:
        for track in self.doc.layout.tracks:
            style = next((c for c in track.curves if c.mnemonic == original), None)
            if style is not None and not any(c.mnemonic == name for c in track.curves):
                track.curves.append(
                    CurveStyle(
                        name,
                        family=style.family,
                        color=style.color,
                        width=style.width,
                        style="dash",
                        left=style.left,
                        right=style.right,
                        log=style.log,
                        unit=style.unit,
                    )
                )
        self.doc.layoutChanged.emit()
