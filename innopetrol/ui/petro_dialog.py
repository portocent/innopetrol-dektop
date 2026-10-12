"""Petrophysics dialog: parameters (also by zone), graphical picking and computation of the results."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from innopetrol.i18n import _
from innopetrol.model import petro, units
from innopetrol.model.calculator import CalculatorError
from innopetrol.model.equations import TEMPERATURE_EQUATIONS
from innopetrol.model.layout import LogLayout
from innopetrol.model.mnemonics import find_curve
from innopetrol.model.petro_layout import place_tracks, results_tracks
from innopetrol.model.tops import zones_from_tops
from innopetrol.resources import app_icon
from innopetrol.ui.document import WellDocument
from innopetrol.ui.equations_dialog import show_equation
from innopetrol.ui.widgets import choice_combo, curve_combo, parse_float, row_of, spin


class PetroDialog(QDialog):
    """Petrophysics parameters in three tabs (Vsh and porosity, water saturation, parameters by zone),
    cutoffs, and the computation of the result curves and tracks."""

    def __init__(self, doc: WellDocument, parent=None):
        super().__init__(parent)
        self.doc = doc
        p = doc.petro or self._initial_params()
        self.zones = zones_from_tops(doc.well.tops, doc.well.stop)
        self.setWindowTitle(_("Petrophysics — {well}").format(well=doc.title))
        self.setWindowIcon(app_icon())
        lay = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._build_vsh_porosity_tab(p), _("Vsh and porosity"))
        tabs.addTab(self._build_saturation_tab(p), _("Water saturation"))
        tabs.addTab(self._build_zones_tab(p), _("Parameters by zone"))
        lay.addWidget(tabs)
        lay.addWidget(self._build_cutoffs(p))
        self.add_track = QCheckBox(_("Add/update a “Petrophysical results” track"))
        self.add_track.setChecked(True)
        lay.addWidget(self.add_track)
        lay.addWidget(QLabel(_("Curves are computed with formulas shown in the well tree and can be exported to LAS.")))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(_("Compute"))
        buttons.accepted.connect(self._run)
        buttons.rejected.connect(self.reject)
        verify = QPushButton(_("Verification workbook (Excel)…"))
        verify.setToolTip(
            _(
                "Saves the inputs, InnoPetrol's results and the same equations as spreadsheet formulas, "
                "to check the calculation in Excel or LibreOffice."
            )
        )
        verify.clicked.connect(self._export_workbook)
        buttons.addButton(verify, QDialogButtonBox.ButtonRole.ActionRole)
        lay.addWidget(buttons)

        self.sw_model.currentIndexChanged.connect(self._update_enabled)
        self.temp_mode.currentIndexChanged.connect(self._update_enabled)
        self.temp_unit.currentIndexChanged.connect(self._temp_unit_changed)
        self._update_enabled()

    # ---------------------------------------------------------------- construction
    def _build_vsh_porosity_tab(self, p: petro.PetroParams) -> QWidget:
        well = self.doc.well
        page = QWidget()
        page_lay = QVBoxLayout(page)
        g1 = QGroupBox(_("Shale volume (Vsh) from gamma ray"))
        f1 = QFormLayout(g1)
        self.gr = curve_combo(well, p.gr_curve)
        self.gr_clean = spin(p.gr_clean, -1000, 10000, 1, 1)
        self.gr_shale = spin(p.gr_shale, -1000, 10000, 1, 1)
        self.vsh_method = choice_combo(petro.VSH_METHODS, p.vsh_method)
        pick_gr = QPushButton(_("Pick on histogram…"))
        pick_gr.clicked.connect(lambda: self._pick_gr(None))
        f1.addRow(_("GR curve:"), self.gr)
        f1.addRow(row_of(QLabel(_("Clean GR")), self.gr_clean, QLabel(_("Shale GR")), self.gr_shale, pick_gr))
        f1.addRow(_("Method:"), self._with_equation(self.vsh_method, lambda: (self.vsh_method.currentData(),)))
        page_lay.addWidget(g1)

        g2 = QGroupBox(_("Porosity"))
        f2 = QFormLayout(g2)
        self.rhob = curve_combo(well, p.rhob_curve)
        self.nphi = curve_combo(well, p.nphi_curve)
        self.rho_ma = spin(p.rho_ma, 1, 4)
        self.rho_fl = spin(p.rho_fl, 0.5, 1.5)
        self.phi_method = choice_combo(petro.PHI_METHODS, p.phi_method)
        f2.addRow(_("Density (RHOB):"), self.rhob)
        f2.addRow(_("Neutron (NPHI):"), self.nphi)
        f2.addRow(row_of(QLabel(_("ρ matrix")), self.rho_ma, QLabel(_("ρ fluid")), self.rho_fl))
        f2.addRow(_("Method:"), self._with_equation(self.phi_method, self._porosity_equations))
        page_lay.addWidget(g2)
        page_lay.addStretch()
        return page

    def _build_saturation_tab(self, p: petro.PetroParams) -> QWidget:
        page = QWidget()
        page_lay = QVBoxLayout(page)
        g3 = QGroupBox(_("Water saturation"))
        f3 = QGridLayout(g3)
        self.rt = curve_combo(self.doc.well, p.rt_curve)
        self.sw_model = choice_combo(petro.SW_MODELS, p.sw_model)
        self.sw_model.setToolTip(
            _(
                "Archie is valid in clean rock. In shaly sands the clay conducts "
                "electricity and Archie overestimates Sw; Simandoux and Indonesia "
                "correct for it using Vsh and the shale resistivity Rsh."
            )
        )
        self.rw = spin(p.rw, 0.001, 100, 0.005, 4)
        self.a = spin(p.a, 0.1, 5)
        self.m = spin(p.m, 1, 4)
        self.n = spin(p.n, 1, 4)
        self.rsh = spin(p.rsh, 0.01, 1000, 0.1, 3)
        f3.addWidget(QLabel(_("Resistivity Rt:")), 0, 0)
        f3.addWidget(self.rt, 0, 1, 1, 9)
        f3.addWidget(QLabel(_("Model:")), 1, 0)
        f3.addWidget(self._with_equation(self.sw_model, lambda: (self.sw_model.currentData(),)), 1, 1, 1, 9)
        for i, (lbl, box) in enumerate(
            (("Rw", self.rw), ("a", self.a), ("m", self.m), ("n", self.n), ("Rsh", self.rsh))
        ):
            f3.addWidget(QLabel(lbl), 2, i * 2)
            f3.addWidget(box, 2, i * 2 + 1)
        pick_rw = QPushButton(_("Pick Rw on Pickett plot…"))
        pick_rw.clicked.connect(lambda: self._pick_rw(None))
        f3.addWidget(pick_rw, 3, 0, 1, 10, Qt.AlignmentFlag.AlignLeft)
        page_lay.addWidget(g3)
        page_lay.addWidget(self._build_temperature(p))
        page_lay.addStretch()
        return page

    def _build_temperature(self, p: petro.PetroParams) -> QGroupBox:
        group = QGroupBox(_("Rw at formation temperature (Arps)"))
        form = QFormLayout(group)
        self.temp_mode = choice_combo(petro.TEMP_MODES, p.temp_mode)
        self.temp_unit = QComboBox()
        self.temp_unit.addItem("°C", "degC")
        self.temp_unit.addItem("°F", "degF")
        self.temp_unit.setCurrentIndex(max(self.temp_unit.findData(p.temp_unit), 0))
        self._temp_unit = p.temp_unit
        self.rw_temp = spin(p.rw_temp, -50, 500, 1, 1)
        self.surface_temp = spin(p.surface_temp, -50, 200, 1, 1)
        self.gradient = spin(p.gradient, 0, 20, 0.1, 2)
        self.temp_curve = curve_combo(self.doc.well, p.temp_curve)
        self.gradient_label = QLabel()
        form.addRow(
            _("Formation temperature:"),
            self._with_equation(self.temp_mode, lambda: TEMPERATURE_EQUATIONS[self.temp_mode.currentData()]),
        )
        form.addRow(_("Temperature unit:"), self.temp_unit)
        form.addRow(_("Rw measured at:"), self.rw_temp)
        form.addRow(_("Surface temperature:"), self.surface_temp)
        form.addRow(self.gradient_label, self.gradient)
        form.addRow(_("Temperature curve:"), self.temp_curve)
        self.temp_form = form
        return group

    def _build_zones_tab(self, p: petro.PetroParams) -> QWidget:
        page = QWidget()
        page_lay = QVBoxLayout(page)
        zone_hint = QLabel(
            _(
                "Parameters that change by formation. An empty cell uses the value of the other "
                "tabs. Zones are the intervals between formation tops."
            )
        )
        zone_hint.setWordWrap(True)
        page_lay.addWidget(zone_hint)
        self.zone_table = QTableWidget(len(self.zones), len(petro.ZONE_PARAMS))
        self.zone_table.setHorizontalHeaderLabels([_(v) for v in petro.ZONE_PARAMS.values()])
        self.zone_table.setVerticalHeaderLabels([f"{z.name}  ({z.top:g}–{z.base:g})" for z in self.zones])
        header = self.zone_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setMinimumSectionSize(52)
        header.setStretchLastSection(True)
        for r, z in enumerate(self.zones):
            for c, key in enumerate(petro.ZONE_PARAMS):
                value = p.zones.get(z.name, {}).get(key)
                self.zone_table.setItem(r, c, QTableWidgetItem("" if value is None else f"{value:g}"))
        page_lay.addWidget(self.zone_table, 1)
        self.zone_pick_gr = QPushButton(_("Pick GR for the selected zone…"))
        self.zone_pick_gr.clicked.connect(lambda: self._pick_gr(self._selected_zone()))
        self.zone_pick_rw = QPushButton(_("Pick Rw for the selected zone…"))
        self.zone_pick_rw.clicked.connect(lambda: self._pick_rw(self._selected_zone()))
        clear = QPushButton(_("Clear the selected zone"))
        clear.clicked.connect(self._clear_zone)
        buttons = row_of(self.zone_pick_gr, self.zone_pick_rw, clear)
        buttons.addStretch()
        page_lay.addLayout(buttons)
        if not self.zones:
            no_tops = QLabel(_("Define formation tops first (Well ▸ Formation tops…)."))
            no_tops.setStyleSheet("color: #b9770e")
            page_lay.addWidget(no_tops)
            page.setEnabled(False)
        return page

    def _with_equation(self, combo: QComboBox, keys) -> QWidget:
        """The combo box with a "?" button that shows the equation of the chosen method."""
        button = QToolButton()
        button.setText("?")
        button.setToolTip(_("Show the equation and its reference"))
        button.clicked.connect(lambda: show_equation(self, keys()))
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(combo, 1)
        row.addWidget(button)
        return box

    def _porosity_equations(self) -> tuple[str, ...]:
        method = self.phi_method.currentData()
        return ("density",) if method == "density" else ("density", method)

    def _build_cutoffs(self, p: petro.PetroParams) -> QGroupBox:
        group = QGroupBox(_("Cutoffs (net reservoir / net pay)"))
        row = QHBoxLayout(group)
        self.vsh_cut = spin(p.vsh_cut, 0, 1)
        self.phi_cut = spin(p.phi_cut, 0, 1)
        self.sw_cut = spin(p.sw_cut, 0, 1)
        for lbl, box in (("Vsh ≤", self.vsh_cut), ("φe ≥", self.phi_cut), ("Sw ≤", self.sw_cut)):
            row.addWidget(QLabel(lbl))
            row.addWidget(box)
        return group

    def _initial_params(self) -> petro.PetroParams:
        """First-time parameters guessed from the well's curves."""
        w = self.doc.well
        p = petro.PetroParams(
            gr_curve=find_curve(w, "gamma_ray"),
            rhob_curve=find_curve(w, "density"),
            nphi_curve=find_curve(w, "neutron"),
            rt_curve=find_curve(w, "deep_res"),
            temp_curve=find_curve(w, "temperature"),
        )
        if p.gr_curve:
            gr = w.curves[p.gr_curve].values
            p.gr_clean, p.gr_shale = (round(float(v), 1) for v in np.nanpercentile(gr, [5, 95]))
            if p.rt_curve:
                # Shale resistivity: median Rt where the gamma ray is highest.
                rt = w.curves[p.rt_curve].values
                shale = gr >= np.nanpercentile(gr, 90)
                rsh = np.nanmedian(rt[shale & np.isfinite(rt) & (rt > 0)]) if shale.any() else np.nan
                if np.isfinite(rsh):
                    p.rsh = round(float(rsh), 2)
        if p.nphi_curve:
            p.phi_method = "nd_average"
        if w.depth_unit == "ft":  # oilfield habits: °F and °F/100 ft
            p.temp_unit, p.surface_temp, p.rw_temp, p.gradient = "degF", 60.0, 75.0, 1.5
        else:
            p.temp_unit, p.surface_temp, p.rw_temp, p.gradient = "degC", 15.0, 24.0, 2.7
        return p

    def _update_enabled(self):
        self.rsh.setEnabled(self.sw_model.currentData() != "archie")
        mode = self.temp_mode.currentData()
        for wdg, on in (
            (self.temp_unit, mode != "none"),
            (self.rw_temp, mode != "none"),
            (self.surface_temp, mode == "gradient"),
            (self.gradient, mode == "gradient"),
            (self.temp_curve, mode == "curve"),
        ):
            wdg.setEnabled(on)
            label = self.temp_form.labelForField(wdg)
            if label is not None:
                label.setEnabled(on)
        unit = self.temp_unit.currentText()
        self.gradient_label.setText(
            _("Gradient ({unit}/100 {depth_unit} TVD):").format(unit=unit, depth_unit=self.doc.well.depth_unit)
        )

    def _temp_unit_changed(self):
        """Converts the temperatures when the unit changes, so the meaning of the values is kept."""
        new = self.temp_unit.currentData()
        old, self._temp_unit = self._temp_unit, new
        if old != new:
            for box in (self.rw_temp, self.surface_temp):
                box.setValue(float(units.convert(box.value(), old, new)))
            self.gradient.setValue(self.gradient.value() * (9 / 5 if new == "degF" else 5 / 9))
        self._update_enabled()

    # ---------------------------------------------------------------- zones
    def _selected_zone(self) -> int | None:
        rows = {i.row() for i in self.zone_table.selectedIndexes()}
        if not rows and self.zone_table.currentRow() >= 0:
            rows = {self.zone_table.currentRow()}
        if len(rows) != 1:
            QMessageBox.information(self, _("Parameters by zone"), _("Select one zone in the table."))
            return -1
        return rows.pop()

    def _clear_zone(self):
        row = self._selected_zone()
        if row is not None and row >= 0:
            for c in range(self.zone_table.columnCount()):
                self.zone_table.item(row, c).setText("")

    def _zone_cell(self, row: int, key: str) -> QTableWidgetItem:
        item = self.zone_table.item(row, list(petro.ZONE_PARAMS).index(key))
        assert item is not None  # every cell is created with the table
        return item

    def _zone_number(self, row: int, key: str, default: float) -> float:
        try:
            value = parse_float(self._zone_cell(row, key).text())
        except ValueError:
            return default
        return default if value is None else value

    def _zone_overrides(self) -> dict[str, dict[str, float]]:
        out: dict[str, dict[str, float]] = {}
        for r, z in enumerate(self.zones):
            for key in petro.ZONE_PARAMS:
                text = self._zone_cell(r, key).text().strip().replace(",", ".")
                if not text:
                    continue
                try:
                    value = float(text)
                except ValueError:
                    raise ValueError(
                        _("Zone {zone}, {parameter}: “{text}” is not a number.").format(
                            zone=z.name, parameter=_(petro.ZONE_PARAMS[key]), text=text
                        )
                    ) from None
                out.setdefault(z.name, {})[key] = value
        return out

    def _set_zone_value(self, row: int, key: str, value: float, default: float):
        self._zone_cell(row, key).setText("" if value == default else f"{value:g}")

    # ---------------------------------------------------------------- graphical picking
    def _interval(self, row: int | None) -> tuple[np.ndarray, str] | None:
        """Mask of the samples to pick from, and its name (None = whole well)."""
        if row is None:
            return np.ones(self.doc.well.depth.shape, bool), _("whole well")
        if row < 0:
            return None
        z = self.zones[row]
        return self.doc.well.interval_mask(z.top, z.base), z.name

    def _pick_gr(self, row: int | None):
        from innopetrol.ui.pickers import GrPickerDialog

        interval = self._interval(row)
        mnem = self.gr.currentData()
        if interval is None:
            return
        if not mnem:
            QMessageBox.information(self, _("Petrophysics"), _("Select the GR curve first."))
            return
        mask, name = interval
        curve = self.doc.well.curves[mnem]
        clean, shale = self.gr_clean.value(), self.gr_shale.value()
        if row is not None:
            clean = self._zone_number(row, "gr_clean", clean)
            shale = self._zone_number(row, "gr_shale", shale)
        label = f"{mnem} ({curve.unit})" if curve.unit else mnem
        dlg = GrPickerDialog(curve.values[mask], clean, shale, label, name, self)
        if dlg.exec():
            clean, shale = dlg.result_values()
            if row is None:
                self.gr_clean.setValue(clean)
                self.gr_shale.setValue(shale)
            else:
                self._set_zone_value(row, "gr_clean", clean, self.gr_clean.value())
                self._set_zone_value(row, "gr_shale", shale, self.gr_shale.value())

    def _pick_rw(self, row: int | None):
        from innopetrol.ui.pickers import PickettPickerDialog

        interval = self._interval(row)
        if interval is None:
            return
        mask, name = interval
        try:
            p = self.params()
        except ValueError as e:
            QMessageBox.warning(self, _("Petrophysics"), str(e))
            return
        if not p.rt_curve or not p.rhob_curve:
            QMessageBox.information(
                self, _("Petrophysics"), _("The Pickett plot needs the resistivity and density curves.")
            )
            return
        # Porosity with the current parameters (Sw is not needed for the plot).
        curves = {c.mnemonic: c for c in petro.compute(self.doc.well, replace(p, rt_curve=None))}
        phie = curves["PHIE"].values
        rt = self.doc.well.curves[p.rt_curve].values
        zone = self.zones[row].name if row is not None else None
        rw, a, m, n = (p.value(k, zone) for k in ("rw", "a", "m", "n"))
        vsh = curves["VSH"].values[mask] if "VSH" in curves else None
        dlg = PickettPickerDialog(rt[mask], phie[mask], rw, a, m, n, name, vsh, self)
        if dlg.exec():
            values = dict(zip(("rw", "a", "m", "n"), dlg.result_values(), strict=True))
            if row is None:
                for key, value in values.items():
                    getattr(self, key).setValue(value)
            else:
                for key, value in values.items():
                    self._set_zone_value(row, key, value, getattr(self, key).value())

    # ---------------------------------------------------------------- compute
    def params(self) -> petro.PetroParams:
        """Parameters in the dialog. Raises ValueError if a zone cell is not a number."""
        return petro.PetroParams(
            gr_curve=self.gr.currentData(),
            gr_clean=self.gr_clean.value(),
            gr_shale=self.gr_shale.value(),
            vsh_method=self.vsh_method.currentData(),
            rhob_curve=self.rhob.currentData(),
            rho_ma=self.rho_ma.value(),
            rho_fl=self.rho_fl.value(),
            nphi_curve=self.nphi.currentData(),
            phi_method=self.phi_method.currentData(),
            rt_curve=self.rt.currentData(),
            rw=self.rw.value(),
            a=self.a.value(),
            m=self.m.value(),
            n=self.n.value(),
            vsh_cut=self.vsh_cut.value(),
            phi_cut=self.phi_cut.value(),
            sw_cut=self.sw_cut.value(),
            sw_model=self.sw_model.currentData(),
            rsh=self.rsh.value(),
            temp_mode=self.temp_mode.currentData(),
            temp_unit=self.temp_unit.currentData(),
            rw_temp=self.rw_temp.value(),
            surface_temp=self.surface_temp.value(),
            gradient=self.gradient.value(),
            temp_curve=self.temp_curve.currentData(),
            zones=self._zone_overrides(),
        )

    def _check(self, p: petro.PetroParams) -> str | None:
        """First problem found in the parameters, checked in every zone, or None."""
        for zone in [None] + [z.name for z in self.zones]:
            where = "" if zone is None else _(" (zone {zone})").format(zone=zone)
            if p.gr_curve and p.value("gr_clean", zone) >= p.value("gr_shale", zone):
                return _("Clean GR must be lower than shale GR.") + where
            if abs(p.value("rho_ma", zone) - p.value("rho_fl", zone)) < 1e-6:
                return _("ρ matrix and ρ fluid cannot be equal.") + where
            if min(p.value(k, zone) for k in ("rw", "a", "m", "n", "rsh")) <= 0:
                return _("Rw, a, m, n and Rsh must be greater than zero.") + where
        if p.temp_mode == "curve" and not p.temp_curve:
            return _("Select the temperature curve.")
        return None

    def _run(self):
        try:
            p = self.params()
        except ValueError as e:
            QMessageBox.warning(self, _("Petrophysics"), str(e))
            return
        problem = self._check(p)
        if problem:
            QMessageBox.warning(self, _("Petrophysics"), problem)
            return
        try:
            curves = petro.compute(self.doc.well, p)
        except CalculatorError as e:
            QMessageBox.critical(self, _("Petrophysics"), _("Calculation error: {error}").format(error=e))
            return
        if not curves:
            QMessageBox.information(self, _("Petrophysics"), _("Select at least the GR or the density curve."))
            return
        with self.doc.undo_step(_("Compute petrophysics")):
            self.doc.petro = p
            self.doc.add_curves(curves)
            if self.add_track.isChecked():
                self._update_results_track([c.mnemonic for c in curves])
        self.accept()

    def _export_workbook(self):
        from innopetrol.model.workbook import verification_workbook

        try:
            p = self.params()
        except ValueError as e:
            QMessageBox.warning(self, _("Petrophysics"), str(e))
            return
        problem = self._check(p)
        if problem:
            QMessageBox.warning(self, _("Petrophysics"), problem)
            return
        path, _filter = QFileDialog.getSaveFileName(
            self, _("Verification workbook"), f"{self.doc.title}_verification.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            n = verification_workbook(path, self.doc.well, p)
        except (OSError, CalculatorError) as e:
            QMessageBox.warning(self, _("Verification workbook"), _("Could not save: {error}").format(error=e))
            return
        QMessageBox.information(
            self, _("Verification workbook"), _("{count} samples written to {path}").format(count=n, path=path)
        )

    def _update_results_track(self, names: list[str]):
        tracks = results_tracks(self.doc.well, names)
        self.doc.adopt_layout(LogLayout(tracks))  # scales in the units the curves are displayed in
        place_tracks(self.doc.layout, tracks)
        self.doc.layoutChanged.emit()
