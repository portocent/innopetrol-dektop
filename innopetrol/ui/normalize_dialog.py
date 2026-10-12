"""Normalize a curve (usually gamma ray) across wells, so the same rock reads the same in every well."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from innopetrol.i18n import _
from innopetrol.model.mnemonics import family_of, find_curve
from innopetrol.model.normalize import normalization_formula, percentiles, zone_mask
from innopetrol.model.well import Curve
from innopetrol.resources import app_icon
from innopetrol.ui.document import WellDocument
from innopetrol.ui.multiwell import checked_docs, equivalent_curve, well_list, zone_names
from innopetrol.ui.widgets import fill_zone_combo, row_of, spin

TYPED = "__typed__"


class NormalizeDialog(QDialog):
    def __init__(self, docs: list[WellDocument], active: WellDocument, parent=None):
        super().__init__(parent)
        self.docs, self.active = docs, active
        self.setWindowTitle(_("Normalize a curve between wells"))
        self.setWindowIcon(app_icon())
        self.resize(720, 620)
        lay = QVBoxLayout(self)
        hint = QLabel(
            _(
                "In each well, the low and high percentiles of the curve inside the zone are taken to the values "
                "of the reference well (or to values you type). The result is a new curve; the original is kept."
            )
        )
        hint.setWordWrap(True)
        lay.addWidget(hint)
        lay.addLayout(self._build_form())
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([_("Well"), _("Curve"), _("Low percentile"), _("High percentile")])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.table, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(_("Normalize"))
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self._connect()
        self._curve_changed()

    def _build_form(self) -> QFormLayout:
        form = QFormLayout()
        self.curve = QComboBox()
        for m in self.active.well.curves:
            self.curve.addItem(m, m)
        self.curve.setCurrentIndex(max(self.curve.findData(find_curve(self.active.well, "gamma_ray")), 0))
        self.wells = well_list(self.docs, self.active)
        for i in range(self.wells.count()):
            self.wells.item(i).setCheckState(Qt.CheckState.Checked)
        self.zone = QComboBox()
        self.low, self.high = spin(5, 0, 50, 1, 0), spin(95, 50, 100, 1, 0)
        self.reference = QComboBox()
        for d in self.docs:
            self.reference.addItem(d.title, d)
        self.reference.addItem(_("Values typed here"), TYPED)
        self.reference.setCurrentIndex(self.reference.findData(self.active))
        self.target_low, self.target_high = spin(20, -1000, 10000, 1, 2), spin(120, -1000, 10000, 1, 2)
        self.name = QLineEdit()
        form.addRow(_("Curve:"), self.curve)
        form.addRow(_("Wells:"), self.wells)
        form.addRow(_("Zone:"), self.zone)
        form.addRow(_("Percentiles (low / high):"), row_of(self.low, self.high))
        form.addRow(_("Reference:"), self.reference)
        form.addRow(_("Target values (low / high):"), row_of(self.target_low, self.target_high))
        form.addRow(_("New curve:"), self.name)
        return form

    def _connect(self) -> None:
        self.curve.currentIndexChanged.connect(self._curve_changed)
        self.wells.itemChanged.connect(self._refresh)
        self.zone.currentIndexChanged.connect(self._refresh)
        self.reference.currentIndexChanged.connect(self._refresh)
        for box in (self.low, self.high):
            box.valueChanged.connect(self._refresh)
        for box in (self.target_low, self.target_high):
            box.valueChanged.connect(self._fill_table)

    def _curve_changed(self) -> None:
        mnemonic = self.curve.currentData()
        self.name.setText("GRN" if family_of(mnemonic or "") == "gamma_ray" else f"{mnemonic}_N")
        self._refresh()

    def _refresh(self) -> None:
        fill_zone_combo(self.zone, zone_names(checked_docs(self.wells)))
        typed = self.reference.currentData() == TYPED
        for box in (self.target_low, self.target_high):
            box.setEnabled(typed)
        if not typed:
            points = self.points(self.reference.currentData())
            if points is not None:
                for box, value in zip((self.target_low, self.target_high), points, strict=True):
                    box.blockSignals(True)
                    box.setValue(round(value, 2))
                    box.blockSignals(False)
        self._fill_table()

    def points(self, doc: WellDocument) -> tuple[float, float] | None:
        """The low and high percentiles of the curve in a well (inside the chosen zone)."""
        mnemonic = equivalent_curve(doc, self.curve.currentData())
        if mnemonic is None:
            return None
        values = doc.well.curves[mnemonic].values
        return percentiles(values, zone_mask(doc.well, self.zone.currentData()), self.low.value(), self.high.value())

    def _fill_table(self) -> None:
        docs = checked_docs(self.wells)
        self.table.setRowCount(len(docs))
        for r, d in enumerate(docs):
            mnemonic = equivalent_curve(d, self.curve.currentData())
            points = self.points(d)
            cells = [d.title, mnemonic or _("(none)")]
            cells += [f"{v:.4g}" for v in points] if points else [_("not enough data")] * 2
            for c, text in enumerate(cells):
                self.table.setItem(r, c, QTableWidgetItem(text))

    def _apply(self) -> None:
        name = self.name.text().strip().upper()
        if not name or not name.replace("_", "").isalnum():
            QMessageBox.warning(self, self.windowTitle(), _("Use a name made of letters, digits or _."))
            return
        reference = self.reference.currentData()
        exact = self.points(reference) if reference != TYPED else None  # the fields show them rounded
        targets = exact or (self.target_low.value(), self.target_high.value())
        if targets[1] <= targets[0]:
            QMessageBox.warning(self, self.windowTitle(), _("The high target must be greater than the low one."))
            return
        done, skipped = [], []
        for d in checked_docs(self.wells):
            if self._normalize(d, name, targets):
                done.append(d.title)
            else:
                skipped.append(d.title)
        message = _("{curve} created in: {wells}").format(curve=name, wells=", ".join(done) or "—")
        if skipped:
            message += "\n" + _(
                "Skipped (no curve, too few samples or an original curve with that name): {wells}"
            ).format(wells=", ".join(skipped))
        QMessageBox.information(self, self.windowTitle(), message)
        self.accept()

    def _normalize(self, doc: WellDocument, name: str, targets: tuple[float, float]) -> bool:
        mnemonic, points = equivalent_curve(doc, self.curve.currentData()), self.points(doc)
        existing = doc.well.curves.get(name)
        if mnemonic is None or points is None or (existing is not None and not existing.formula):
            return False
        source = doc.well.curves[mnemonic]
        (lo, hi), (t_lo, t_hi) = points, targets
        values = t_lo + (source.values - lo) * (t_hi - t_lo) / (hi - lo)
        description = _("{curve} normalized (P{low:g}–P{high:g} → {t_low:g}–{t_high:g})").format(
            curve=mnemonic, low=self.low.value(), high=self.high.value(), t_low=t_lo, t_high=t_hi
        )
        with doc.undo_step(_("Normalize {curve}").format(curve=mnemonic)):
            doc.add_curves(
                [
                    Curve(
                        name, source.unit, description, values, formula=normalization_formula(mnemonic, points, targets)
                    )
                ]
            )
        return True
