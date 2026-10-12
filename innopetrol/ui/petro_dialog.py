"""Calculation dialogs: basic petrophysics, curve calculator and zone summary."""

from __future__ import annotations

import csv

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout)

from innopetrol.i18n import _
from innopetrol.model import petro
from innopetrol.model.calculator import CalculatorError, FUNCTIONS, curve_ref, evaluate
from innopetrol.model.layout import CurveStyle, FillSpec, TrackSpec
from innopetrol.model.mnemonics import find_curve, make_curve_style
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
        p = doc.petro or petro.PetroParams(
            gr_curve=find_curve(w, "gamma_ray"), rhob_curve=find_curve(w, "density"),
            nphi_curve=find_curve(w, "neutron"), rt_curve=find_curve(w, "deep_res"),
        )
        if doc.petro is None and p.gr_curve:
            gr = w.curves[p.gr_curve].values
            p.gr_clean, p.gr_shale = (round(float(v), 1) for v in np.nanpercentile(gr, [5, 95]))
        if doc.petro is None and p.nphi_curve:
            p.phi_method = "nd_average"
        self.setWindowTitle(_("Basic petrophysics — {well}").format(well=doc.title))
        self.setWindowIcon(app_icon())
        lay = QVBoxLayout(self)

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
        f1.addRow(_("GR curve:"), self.gr)
        f1.addRow(gr_row)
        f1.addRow(_("Method:"), self.vsh_method)
        lay.addWidget(g1)

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
        lay.addWidget(g2)

        g3 = QGroupBox(_("Water saturation — Archie"))
        f3 = QGridLayout(g3)
        self.rt = _curve_combo(doc, p.rt_curve)
        self.rw = _spin(p.rw, 0.001, 100, 0.005, 4)
        self.a = _spin(p.a, 0.1, 5)
        self.m = _spin(p.m, 1, 4)
        self.n = _spin(p.n, 1, 4)
        f3.addWidget(QLabel(_("Resistivity Rt:")), 0, 0)
        f3.addWidget(self.rt, 0, 1, 1, 7)
        for i, (lbl, s) in enumerate((("Rw", self.rw), ("a", self.a), ("m", self.m), ("n", self.n))):
            f3.addWidget(QLabel(lbl), 1, i * 2)
            f3.addWidget(s, 1, i * 2 + 1)
        lay.addWidget(g3)

        g4 = QGroupBox(_("Cutoffs (net reservoir / net pay)"))
        f4 = QHBoxLayout(g4)
        self.vsh_cut = _spin(p.vsh_cut, 0, 1)
        self.phi_cut = _spin(p.phi_cut, 0, 1)
        self.sw_cut = _spin(p.sw_cut, 0, 1)
        for lbl, s in (("Vsh ≤", self.vsh_cut), ("φe ≥", self.phi_cut), ("Sw ≤", self.sw_cut)):
            f4.addWidget(QLabel(lbl))
            f4.addWidget(s)
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

    def params(self) -> petro.PetroParams:
        return petro.PetroParams(
            gr_curve=self.gr.currentData(), gr_clean=self.gr_clean.value(), gr_shale=self.gr_shale.value(),
            vsh_method=self.vsh_method.currentData(), rhob_curve=self.rhob.currentData(),
            rho_ma=self.rho_ma.value(), rho_fl=self.rho_fl.value(), nphi_curve=self.nphi.currentData(),
            phi_method=self.phi_method.currentData(), rt_curve=self.rt.currentData(), rw=self.rw.value(),
            a=self.a.value(), m=self.m.value(), n=self.n.value(), vsh_cut=self.vsh_cut.value(),
            phi_cut=self.phi_cut.value(), sw_cut=self.sw_cut.value(),
        )

    def _run(self):
        p = self.params()
        if p.gr_clean >= p.gr_shale and p.gr_curve:
            QMessageBox.warning(self, _("Petrophysics"), _("Clean GR must be lower than shale GR."))
            return
        if abs(p.rho_ma - p.rho_fl) < 1e-6:
            QMessageBox.warning(self, _("Petrophysics"), _("ρ matrix and ρ fluid cannot be equal."))
            return
        try:
            curves = petro.compute(self.doc.well, p)
        except CalculatorError as e:
            QMessageBox.critical(self, _("Petrophysics"), _("Calculation error: {error}").format(error=e))
            return
        if not curves:
            QMessageBox.information(self, _("Petrophysics"), _("Select at least the GR or the density curve."))
            return
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
        tracks = self.doc.layout.tracks

        # Tracks are found by the curves they contain, never by title: titles depend on the
        # language that was active when the layout was created.
        def find(mnemonics=(), families=()):
            for i, t in enumerate(tracks):
                if any(c.mnemonic in mnemonics or (c.family and c.family in families) for c in t.curves):
                    return i
            return None

        # Placed next to the density-neutron track (or resistivity) so they are visible right away.
        anchor = find(families=("density", "neutron"))
        if anchor is None:
            anchor = find(families=("deep_res",))
        if anchor is None:
            anchor = len(tracks) - 1
        for new, owned in ((track, ("VSH", "PHIE", "SW")), (flag_track, ("RES_FLAG", "PAY_FLAG"))):
            if new is None:
                continue
            idx = find(mnemonics=owned)
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
            return evaluate(self.expr.toPlainText(), {m: c.values for m, c in self.doc.well.curves.items()})
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
        self.doc.add_curves([Curve(name, self.unit.text().strip(), self.descr.text().strip() or _("Computed curve"),
                                   v, formula=formula)])
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
        rows = petro.zone_summary(self.doc.well, self._zones(), self.vsh.currentData(), self.phi.currentData(),
                                  self.sw.currentData(), self.vsh_cut.value(), self.phi_cut.value(),
                                  self.sw_cut.value())
        self.note.setText("" if self.doc.well.tops else
                          _("No tops defined: the whole well is summarized (Well ▸ Formation tops…)."))
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
