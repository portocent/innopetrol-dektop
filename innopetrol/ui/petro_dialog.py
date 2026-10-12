"""Calculation dialogs: basic petrophysics, curve calculator and zone summary."""

from __future__ import annotations

import csv
from dataclasses import replace

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from innopetrol.i18n import _
from innopetrol.model import petro, units
from innopetrol.model.calculator import FUNCTIONS, CalculatorError, curve_ref, evaluate
from innopetrol.model.layout import CurveStyle, FillSpec, LogLayout, TrackSpec
from innopetrol.model.mnemonics import build_volumes_track, find_curve, make_curve_style
from innopetrol.model.tops import Zone, zones_from_tops
from innopetrol.model.well import Curve
from innopetrol.resources import app_icon
from innopetrol.ui.document import WellDocument


def _spin(value, lo, hi, step=0.01, decimals=3):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(decimals)
    s.setSingleStep(step)
    s.setValue(value)
    return s


def _curve_combo(doc: WellDocument, current: str | None, optional=True) -> QComboBox:
    c = QComboBox()
    if optional:
        c.addItem(_("(none)"), None)
    for m, curve in doc.well.curves.items():
        c.addItem(f"{m}  [{curve.unit}]" if curve.unit else m, m)
    c.setCurrentIndex(max(c.findData(current), 0))
    return c


# ============================================================================ petrophysics


class PetroDialog(QDialog):
    def __init__(self, doc: WellDocument, parent=None):
        super().__init__(parent)
        self.doc = doc
        w = doc.well
        p = doc.petro or self._initial_params()
        self.zones = zones_from_tops(w.tops, w.stop)
        self.setWindowTitle(_("Petrophysics — {well}").format(well=doc.title))
        self.setWindowIcon(app_icon())
        lay = QVBoxLayout(self)
        tabs = QTabWidget()
        lay.addWidget(tabs)

        # ---------------------------------------------------------------- Vsh and porosity
        page = QWidget()
        page_lay = QVBoxLayout(page)
        g1 = QGroupBox(_("Shale volume (Vsh) from gamma ray"))
        f1 = QFormLayout(g1)
        self.gr = _curve_combo(doc, p.gr_curve)
        self.gr_clean = _spin(p.gr_clean, -1000, 10000, 1, 1)
        self.gr_shale = _spin(p.gr_shale, -1000, 10000, 1, 1)
        self.vsh_method = QComboBox()
        for k, v in petro.VSH_METHODS.items():
            self.vsh_method.addItem(_(v), k)
        self.vsh_method.setCurrentIndex(self.vsh_method.findData(p.vsh_method))
        gr_row = QHBoxLayout()
        gr_row.addWidget(QLabel(_("Clean GR")))
        gr_row.addWidget(self.gr_clean)
        gr_row.addWidget(QLabel(_("Shale GR")))
        gr_row.addWidget(self.gr_shale)
        pick_gr = QPushButton(_("Pick on histogram…"))
        pick_gr.clicked.connect(lambda: self._pick_gr(None))
        gr_row.addWidget(pick_gr)
        f1.addRow(_("GR curve:"), self.gr)
        f1.addRow(gr_row)
        f1.addRow(_("Method:"), self.vsh_method)
        page_lay.addWidget(g1)

        g2 = QGroupBox(_("Porosity"))
        f2 = QFormLayout(g2)
        self.rhob = _curve_combo(doc, p.rhob_curve)
        self.nphi = _curve_combo(doc, p.nphi_curve)
        self.rho_ma = _spin(p.rho_ma, 1, 4)
        self.rho_fl = _spin(p.rho_fl, 0.5, 1.5)
        self.phi_method = QComboBox()
        for k, v in petro.PHI_METHODS.items():
            self.phi_method.addItem(_(v), k)
        self.phi_method.setCurrentIndex(self.phi_method.findData(p.phi_method))
        rho_row = QHBoxLayout()
        rho_row.addWidget(QLabel(_("ρ matrix")))
        rho_row.addWidget(self.rho_ma)
        rho_row.addWidget(QLabel(_("ρ fluid")))
        rho_row.addWidget(self.rho_fl)
        f2.addRow(_("Density (RHOB):"), self.rhob)
        f2.addRow(_("Neutron (NPHI):"), self.nphi)
        f2.addRow(rho_row)
        f2.addRow(_("Method:"), self.phi_method)
        page_lay.addWidget(g2)
        page_lay.addStretch()
        tabs.addTab(page, _("Vsh and porosity"))

        # ---------------------------------------------------------------- water saturation
        page = QWidget()
        page_lay = QVBoxLayout(page)
        g3 = QGroupBox(_("Water saturation"))
        f3 = QGridLayout(g3)
        self.rt = _curve_combo(doc, p.rt_curve)
        self.sw_model = QComboBox()
        for k, v in petro.SW_MODELS.items():
            self.sw_model.addItem(_(v), k)
        self.sw_model.setCurrentIndex(max(self.sw_model.findData(p.sw_model), 0))
        self.sw_model.setToolTip(_("Archie is valid in clean rock. In shaly sands the clay conducts "
                                   "electricity and Archie overestimates Sw; Simandoux and Indonesia "
                                   "correct for it using Vsh and the shale resistivity Rsh."))
        self.rw = _spin(p.rw, 0.001, 100, 0.005, 4)
        self.a = _spin(p.a, 0.1, 5)
        self.m = _spin(p.m, 1, 4)
        self.n = _spin(p.n, 1, 4)
        self.rsh = _spin(p.rsh, 0.01, 1000, 0.1, 3)
        f3.addWidget(QLabel(_("Resistivity Rt:")), 0, 0)
        f3.addWidget(self.rt, 0, 1, 1, 9)
        f3.addWidget(QLabel(_("Model:")), 1, 0)
        f3.addWidget(self.sw_model, 1, 1, 1, 9)
        for i, (lbl, spin) in enumerate((("Rw", self.rw), ("a", self.a), ("m", self.m), ("n", self.n),
                                         ("Rsh", self.rsh))):
            f3.addWidget(QLabel(lbl), 2, i * 2)
            f3.addWidget(spin, 2, i * 2 + 1)
        pick_rw = QPushButton(_("Pick Rw on Pickett plot…"))
        pick_rw.clicked.connect(lambda: self._pick_rw(None))
        f3.addWidget(pick_rw, 3, 0, 1, 10, Qt.AlignLeft)
        page_lay.addWidget(g3)

        g5 = QGroupBox(_("Rw at formation temperature (Arps)"))
        f5 = QFormLayout(g5)
        self.temp_mode = QComboBox()
        for k, v in petro.TEMP_MODES.items():
            self.temp_mode.addItem(_(v), k)
        self.temp_mode.setCurrentIndex(max(self.temp_mode.findData(p.temp_mode), 0))
        self.temp_unit = QComboBox()
        self.temp_unit.addItem("°C", "degC")
        self.temp_unit.addItem("°F", "degF")
        self.temp_unit.setCurrentIndex(max(self.temp_unit.findData(p.temp_unit), 0))
        self._temp_unit = p.temp_unit
        self.rw_temp = _spin(p.rw_temp, -50, 500, 1, 1)
        self.surface_temp = _spin(p.surface_temp, -50, 200, 1, 1)
        self.gradient = _spin(p.gradient, 0, 20, 0.1, 2)
        self.temp_curve = _curve_combo(doc, p.temp_curve)
        self.gradient_label = QLabel()
        f5.addRow(_("Formation temperature:"), self.temp_mode)
        f5.addRow(_("Temperature unit:"), self.temp_unit)
        f5.addRow(_("Rw measured at:"), self.rw_temp)
        f5.addRow(_("Surface temperature:"), self.surface_temp)
        f5.addRow(self.gradient_label, self.gradient)
        f5.addRow(_("Temperature curve:"), self.temp_curve)
        self.temp_form = f5
        page_lay.addWidget(g5)
        page_lay.addStretch()
        tabs.addTab(page, _("Water saturation"))

        # ---------------------------------------------------------------- zones
        page = QWidget()
        page_lay = QVBoxLayout(page)
        zone_hint = QLabel(_("Parameters that change by formation. An empty cell uses the value of the other "
                             "tabs. Zones are the intervals between formation tops."))
        zone_hint.setWordWrap(True)
        page_lay.addWidget(zone_hint)
        self.zone_table = QTableWidget(len(self.zones), len(petro.ZONE_PARAMS))
        self.zone_table.setHorizontalHeaderLabels([_(v) for v in petro.ZONE_PARAMS.values()])
        self.zone_table.setVerticalHeaderLabels([f"{z.name}  ({z.top:g}–{z.base:g})" for z in self.zones])
        self.zone_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.zone_table.horizontalHeader().setMinimumSectionSize(52)
        self.zone_table.horizontalHeader().setStretchLastSection(True)
        for r, z in enumerate(self.zones):
            for c, key in enumerate(petro.ZONE_PARAMS):
                value = p.zones.get(z.name, {}).get(key)
                self.zone_table.setItem(r, c, QTableWidgetItem("" if value is None else f"{value:g}"))
        page_lay.addWidget(self.zone_table, 1)
        zone_buttons = QHBoxLayout()
        self.zone_pick_gr = QPushButton(_("Pick GR for the selected zone…"))
        self.zone_pick_gr.clicked.connect(lambda: self._pick_gr(self._selected_zone()))
        self.zone_pick_rw = QPushButton(_("Pick Rw for the selected zone…"))
        self.zone_pick_rw.clicked.connect(lambda: self._pick_rw(self._selected_zone()))
        clear = QPushButton(_("Clear the selected zone"))
        clear.clicked.connect(self._clear_zone)
        for b in (self.zone_pick_gr, self.zone_pick_rw, clear):
            zone_buttons.addWidget(b)
        zone_buttons.addStretch()
        page_lay.addLayout(zone_buttons)
        if not self.zones:
            no_tops = QLabel(_("Define formation tops first (Well ▸ Formation tops…)."))
            no_tops.setStyleSheet("color: #b9770e")
            page_lay.addWidget(no_tops)
            page.setEnabled(False)
        tabs.addTab(page, _("Parameters by zone"))

        g4 = QGroupBox(_("Cutoffs (net reservoir / net pay)"))
        f4 = QHBoxLayout(g4)
        self.vsh_cut = _spin(p.vsh_cut, 0, 1)
        self.phi_cut = _spin(p.phi_cut, 0, 1)
        self.sw_cut = _spin(p.sw_cut, 0, 1)
        for lbl, spin in (("Vsh ≤", self.vsh_cut), ("φe ≥", self.phi_cut), ("Sw ≤", self.sw_cut)):
            f4.addWidget(QLabel(lbl))
            f4.addWidget(spin)
        lay.addWidget(g4)

        self.add_track = QCheckBox(_("Add/update a “Petrophysical results” track"))
        self.add_track.setChecked(True)
        lay.addWidget(self.add_track)
        lay.addWidget(QLabel(_("Curves are computed with formulas shown in the well tree and can be "
                               "exported to LAS.")))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(_("Compute"))
        buttons.accepted.connect(self._run)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        self.sw_model.currentIndexChanged.connect(self._update_enabled)
        self.temp_mode.currentIndexChanged.connect(self._update_enabled)
        self.temp_unit.currentIndexChanged.connect(self._temp_unit_changed)
        self._update_enabled()

    def _initial_params(self) -> petro.PetroParams:
        """First-time parameters guessed from the well's curves."""
        w = self.doc.well
        p = petro.PetroParams(
            gr_curve=find_curve(w, "gamma_ray"), rhob_curve=find_curve(w, "density"),
            nphi_curve=find_curve(w, "neutron"), rt_curve=find_curve(w, "deep_res"),
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
        for wdg, on in ((self.temp_unit, mode != "none"), (self.rw_temp, mode != "none"),
                        (self.surface_temp, mode == "gradient"), (self.gradient, mode == "gradient"),
                        (self.temp_curve, mode == "curve")):
            wdg.setEnabled(on)
            label = self.temp_form.labelForField(wdg)
            if label is not None:
                label.setEnabled(on)
        unit = self.temp_unit.currentText()
        self.gradient_label.setText(_("Gradient ({unit}/100 {depth_unit} TVD):").format(
            unit=unit, depth_unit=self.doc.well.depth_unit))

    def _temp_unit_changed(self):
        """Converts the temperatures when the unit changes, so the meaning of the values is kept."""
        new = self.temp_unit.currentData()
        old, self._temp_unit = self._temp_unit, new
        if old != new:
            for spin in (self.rw_temp, self.surface_temp):
                spin.setValue(float(units.convert(spin.value(), old, new)))
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
        return self.zone_table.item(row, list(petro.ZONE_PARAMS).index(key))

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
                    raise ValueError(_("Zone {zone}, {parameter}: “{text}” is not a number.").format(
                        zone=z.name, parameter=_(petro.ZONE_PARAMS[key]), text=text)) from None
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
            clean = _float(self._zone_cell(row, "gr_clean").text(), clean)
            shale = _float(self._zone_cell(row, "gr_shale").text(), shale)
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
            QMessageBox.information(self, _("Petrophysics"),
                                    _("The Pickett plot needs the resistivity and density curves."))
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
            values = dict(zip(("rw", "a", "m", "n"), dlg.result_values()))
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
            gr_curve=self.gr.currentData(), gr_clean=self.gr_clean.value(), gr_shale=self.gr_shale.value(),
            vsh_method=self.vsh_method.currentData(), rhob_curve=self.rhob.currentData(),
            rho_ma=self.rho_ma.value(), rho_fl=self.rho_fl.value(), nphi_curve=self.nphi.currentData(),
            phi_method=self.phi_method.currentData(), rt_curve=self.rt.currentData(), rw=self.rw.value(),
            a=self.a.value(), m=self.m.value(), n=self.n.value(), vsh_cut=self.vsh_cut.value(),
            phi_cut=self.phi_cut.value(), sw_cut=self.sw_cut.value(), sw_model=self.sw_model.currentData(),
            rsh=self.rsh.value(), temp_mode=self.temp_mode.currentData(), temp_unit=self.temp_unit.currentData(),
            rw_temp=self.rw_temp.value(), surface_temp=self.surface_temp.value(), gradient=self.gradient.value(),
            temp_curve=self.temp_curve.currentData(), zones=self._zone_overrides(),
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

    def _update_results_track(self, names: list[str]):
        w = self.doc.well
        styles = [make_curve_style(w, m) for m in ("VSH", "PHIE", "SW") if m in names]
        track = TrackSpec(title=_("Petrophysical results"), width=220, curves=styles)
        if "VSH" in names:
            track.fills.append(FillSpec(left_value=0, right_curve="VSH", color="#a0522d", pattern="dense3",
                                        label="Vsh"))
        if "PHIE" in names:
            track.fills.append(FillSpec(left_curve="PHIE", right_value=0, color="#5dade2", pattern="solid",
                                        label="φe"))
        flags = [m for m in ("RES_FLAG", "PAY_FLAG") if m in names]
        flag_track = None
        if flags:
            flag_track = TrackSpec(title=_("Net res / pay"), width=70, grid="none",
                                   curves=[CurveStyle(m, color=c, left=0, right=1, visible=False)
                                           for m, c in zip(flags, ("#27ae60", "#c0392b"))])
            colors = {"RES_FLAG": "#82e0aa", "PAY_FLAG": "#e74c3c"}
            for m in flags:
                flag_track.fills.append(FillSpec(left_value=0, right_curve=m, color=colors[m],
                                                 label=_("Reservoir") if m == "RES_FLAG" else _("Pay")))
        volumes = build_volumes_track(w)
        if volumes is not None:
            self.doc.adopt_layout(LogLayout([volumes]))  # in the units the curves are displayed in
        tracks = self.doc.layout.tracks

        # Tracks are found by the curves they contain, never by title: titles depend on the
        # language that was active when the layout was created.
        def find(mnemonics=(), families=(), kind="curves"):
            for i, t in enumerate(tracks):
                if t.kind == kind and any(c.mnemonic in mnemonics or (c.family and c.family in families)
                                          for c in t.curves):
                    return i
            return None

        # Placed next to the density-neutron track (or resistivity) so they are visible right away.
        anchor = find(families=("density", "neutron"))
        if anchor is None:
            anchor = find(families=("deep_res",))
        if anchor is None:
            anchor = len(tracks) - 1
        for new, owned in ((track, ("VSH", "PHIE", "SW")), (flag_track, ("RES_FLAG", "PAY_FLAG")),
                           (volumes, ("VMAT",))):
            if new is None:
                continue
            idx = find(mnemonics=owned, kind=new.kind)
            if idx is None:
                anchor += 1
                tracks.insert(anchor, new)
            else:
                tracks[idx] = new
                anchor = idx
        self.doc.layoutChanged.emit()


# ============================================================================ calculator


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
        self.expr.setPlaceholderText(_("E.g.: (2.65 - RHOB) / (2.65 - 1.0)") + "\n     where(GR > 75, 1, 0)\n     log10(LLD)")
        left.addWidget(self.expr, 1)
        help_text = "\n".join([
            _("Operators: {operators}").format(operators="+ - * / ** < > <= >= == & |"),
            _("Functions: {functions}").format(functions=", ".join(sorted(FUNCTIONS))),
            _("Constants: pi, e, nan. Curves with special names: [K-3104]"),
            _("DEPTH and TVD: depth of each sample (measured and true vertical, in the file's depth unit)."),
        ])
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
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(_("Create curve"))
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
            item.setData(Qt.UserRole, m)
            self.list.addItem(item)
        self.list.itemDoubleClicked.connect(lambda it: self.expr.insertPlainText(curve_ref(it.data(Qt.UserRole))))
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
                self.preview.setText(_("Valid: {count} samples · min {min} · max {max} · mean {mean}").format(
                    count=n, min=f"{np.nanmin(v):.4g}", max=f"{np.nanmax(v):.4g}", mean=f"{np.nanmean(v):.4g}"))
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
            QMessageBox.warning(self, _("Calculator"),
                                _("{name} is an original LAS curve; choose another name.").format(name=name))
            return
        formula = " ".join(self.expr.toPlainText().split())
        with self.doc.undo_step(_("Create curve {name}").format(name=name)):
            self.doc.add_curves([Curve(name, self.unit.text().strip(),
                                       self.descr.text().strip() or _("Computed curve"), v, formula=formula)])
        self.accept()


# ============================================================================ zone summary


class ZoneSummaryDialog(QDialog):
    def __init__(self, doc: WellDocument, parent=None):
        super().__init__(parent)
        self.doc = doc
        w = doc.well
        p = doc.petro or petro.PetroParams()
        self.setWindowTitle(_("Zone summary — {well}").format(well=doc.title))
        self.setWindowIcon(app_icon())
        self.resize(900, 420)
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        self.vsh = _curve_combo(doc, "VSH" if "VSH" in w.curves else find_curve(w, "vsh"))
        self.phi = _curve_combo(doc, "PHIE" if "PHIE" in w.curves else find_curve(w, "effective_porosity"))
        self.sw = _curve_combo(doc, "SW" if "SW" in w.curves else find_curve(w, "sw"))
        self.vsh_cut = _spin(p.vsh_cut, 0, 1)
        self.phi_cut = _spin(p.phi_cut, 0, 1)
        self.sw_cut = _spin(p.sw_cut, 0, 1)
        for lbl, wdg in (("Vsh", self.vsh), ("≤", self.vsh_cut), ("φ", self.phi), ("≥", self.phi_cut),
                         ("Sw", self.sw), ("≤", self.sw_cut)):
            row.addWidget(QLabel(lbl))
            row.addWidget(wdg)
        calc = QPushButton(_("Compute"))
        calc.clicked.connect(self._calc)
        row.addWidget(calc)
        lay.addLayout(row)
        self.note = QLabel()
        lay.addWidget(self.note)
        self.table = QTableWidget(0, 10)
        u = w.depth_unit
        self.table.setHorizontalHeaderLabels([
            _("Zone"), _("Top ({unit})").format(unit=u), _("Base ({unit})").format(unit=u),
            _("Gross ({unit})").format(unit=u), _("Net res. ({unit})").format(unit=u),
            _("Net pay ({unit})").format(unit=u), "N/G", _("Avg φ"), _("Avg Sw"), _("Avg Vsh")])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # zone names
        lay.addWidget(self.table, 1)
        out = QHBoxLayout()
        copy_btn = QPushButton(_("Copy (for Excel)"))
        copy_btn.clicked.connect(self._copy)
        save_btn = QPushButton(_("Save CSV…"))
        save_btn.clicked.connect(self._save)
        out.addWidget(copy_btn)
        out.addWidget(save_btn)
        out.addStretch()
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.reject)
        out.addWidget(close)
        lay.addLayout(out)
        self._rows: list[list[str]] = []
        self._calc()

    def _zones(self) -> list[Zone]:
        w = self.doc.well
        if w.tops:
            zones = zones_from_tops(w.tops, w.stop)
            first = min(t.depth for t in w.tops)
            if first > w.start:
                zones.insert(0, Zone(_("(above the first top)"), w.start, first))
            return zones
        return [Zone(_("Whole well"), w.start, w.stop)]

    def _calc(self):
        cutoffs = {}
        if self.doc.petro is not None:  # cutoffs set per zone in the petrophysics dialog
            cutoffs = {z: {k: v for k, v in vals.items() if k in ("vsh_cut", "phi_cut", "sw_cut")}
                       for z, vals in self.doc.petro.zones.items()}
            cutoffs = {z: v for z, v in cutoffs.items() if v}
        rows = petro.zone_summary(self.doc.well, self._zones(), self.vsh.currentData(), self.phi.currentData(),
                                  self.sw.currentData(), self.vsh_cut.value(), self.phi_cut.value(),
                                  self.sw_cut.value(), cutoffs)
        notes = []
        if not self.doc.well.tops:
            notes.append(_("No tops defined: the whole well is summarized (Well ▸ Formation tops…)."))
        used = [r.zone for r in rows if r.zone in cutoffs]
        if used:
            notes.append(_("Zones with their own cutoffs (from Petrophysics ▸ Parameters by zone): {zones}").format(
                zones=", ".join(used)))
        self.note.setText("\n".join(notes))
        self._rows = []
        self.table.setRowCount(len(rows))
        for r, z in enumerate(rows):
            vals = [z.zone, f"{z.top:.1f}", f"{z.base:.1f}", f"{z.gross:.1f}", f"{z.net_reservoir:.1f}",
                    f"{z.net_pay:.1f}", _pct(z.ntg), _num(z.phi_avg), _num(z.sw_avg), _num(z.vsh_avg)]
            self._rows.append(vals)
            for c, v in enumerate(vals):
                item = QTableWidgetItem(v)
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter if c else Qt.AlignLeft | Qt.AlignVCenter)
                self.table.setItem(r, c, item)

    def _headers(self):
        return [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]

    def _copy(self):
        text = "\n".join("\t".join(r) for r in [self._headers()] + self._rows)
        QGuiApplication.clipboard().setText(text)

    def _save(self):
        path, _filter = QFileDialog.getSaveFileName(self, _("Save summary"), f"{self.doc.title}_zones.csv",
                                                     "CSV (*.csv)")
        if path:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:  # BOM: Excel on Windows
                csv.writer(f).writerows([self._headers()] + self._rows)


def _num(v: float) -> str:
    return "—" if not np.isfinite(v) else f"{v:.3f}"


def _pct(v: float) -> str:
    return "—" if not np.isfinite(v) else f"{v * 100:.0f} %"


def _float(text: str, default: float) -> float:
    try:
        return float(text.strip().replace(",", "."))
    except ValueError:
        return default
