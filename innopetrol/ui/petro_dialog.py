"""Diálogos de cálculo: petrofísica básica, calculadora de curvas y resumen por zonas."""

from __future__ import annotations

import csv

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QListWidget, QMessageBox, QPlainTextEdit, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout)

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
        c.addItem("(ninguna)", None)
    for m, curve in doc.well.curves.items():
        c.addItem(f"{m}  [{curve.unit}]" if curve.unit else m, m)
    c.setCurrentIndex(max(c.findData(current), 0))
    return c


# ============================================================================ petrofísica


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
        self.setWindowTitle(f"Petrofísica básica — {doc.title}")
        self.setWindowIcon(app_icon())
        lay = QVBoxLayout(self)

        g1 = QGroupBox("Volumen de arcilla (Vsh) desde rayos gamma")
        f1 = QFormLayout(g1)
        self.gr = _curve_combo(doc, p.gr_curve)
        self.gr_clean = _spin(p.gr_clean, -1000, 10000, 1, 1)
        self.gr_shale = _spin(p.gr_shale, -1000, 10000, 1, 1)
        self.vsh_method = QComboBox()
        for k, v in petro.VSH_METHODS.items():
            self.vsh_method.addItem(v, k)
        self.vsh_method.setCurrentIndex(self.vsh_method.findData(p.vsh_method))
        gr_row = QHBoxLayout()
        gr_row.addWidget(QLabel("GR limpio"))
        gr_row.addWidget(self.gr_clean)
        gr_row.addWidget(QLabel("GR arcilla"))
        gr_row.addWidget(self.gr_shale)
        f1.addRow("Curva GR:", self.gr)
        f1.addRow(gr_row)
        f1.addRow("Método:", self.vsh_method)
        lay.addWidget(g1)

        g2 = QGroupBox("Porosidad")
        f2 = QFormLayout(g2)
        self.rhob = _curve_combo(doc, p.rhob_curve)
        self.nphi = _curve_combo(doc, p.nphi_curve)
        self.rho_ma = _spin(p.rho_ma, 1, 4)
        self.rho_fl = _spin(p.rho_fl, 0.5, 1.5)
        self.phi_method = QComboBox()
        for k, v in petro.PHI_METHODS.items():
            self.phi_method.addItem(v, k)
        self.phi_method.setCurrentIndex(self.phi_method.findData(p.phi_method))
        rho_row = QHBoxLayout()
        rho_row.addWidget(QLabel("ρ matriz"))
        rho_row.addWidget(self.rho_ma)
        rho_row.addWidget(QLabel("ρ fluido"))
        rho_row.addWidget(self.rho_fl)
        f2.addRow("Densidad (RHOB):", self.rhob)
        f2.addRow("Neutrón (NPHI):", self.nphi)
        f2.addRow(rho_row)
        f2.addRow("Método:", self.phi_method)
        lay.addWidget(g2)

        g3 = QGroupBox("Saturación de agua — Archie")
        f3 = QGridLayout(g3)
        self.rt = _curve_combo(doc, p.rt_curve)
        self.rw = _spin(p.rw, 0.001, 100, 0.005, 4)
        self.a = _spin(p.a, 0.1, 5)
        self.m = _spin(p.m, 1, 4)
        self.n = _spin(p.n, 1, 4)
        f3.addWidget(QLabel("Resistividad Rt:"), 0, 0)
        f3.addWidget(self.rt, 0, 1, 1, 7)
        for i, (lbl, s) in enumerate((("Rw", self.rw), ("a", self.a), ("m", self.m), ("n", self.n))):
            f3.addWidget(QLabel(lbl), 1, i * 2)
            f3.addWidget(s, 1, i * 2 + 1)
        lay.addWidget(g3)

        g4 = QGroupBox("Cortes (net reservoir / net pay)")
        f4 = QHBoxLayout(g4)
        self.vsh_cut = _spin(p.vsh_cut, 0, 1)
        self.phi_cut = _spin(p.phi_cut, 0, 1)
        self.sw_cut = _spin(p.sw_cut, 0, 1)
        for lbl, s in (("Vsh ≤", self.vsh_cut), ("φe ≥", self.phi_cut), ("Sw ≤", self.sw_cut)):
            f4.addWidget(QLabel(lbl))
            f4.addWidget(s)
        lay.addWidget(g4)

        self.add_track = QCheckBox("Agregar/actualizar un track «Resultados petrofísicos»")
        self.add_track.setChecked(True)
        lay.addWidget(self.add_track)
        lay.addWidget(QLabel("Las curvas se calculan con fórmulas visibles en el árbol del pozo y se pueden "
                             "exportar a LAS."))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Calcular")
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
            QMessageBox.warning(self, "Petrofísica", "GR limpio debe ser menor que GR arcilla.")
            return
        if abs(p.rho_ma - p.rho_fl) < 1e-6:
            QMessageBox.warning(self, "Petrofísica", "ρ matriz y ρ fluido no pueden ser iguales.")
            return
        try:
            curves = petro.compute(self.doc.well, p)
        except CalculatorError as e:
            QMessageBox.critical(self, "Petrofísica", f"Error en el cálculo: {e}")
            return
        if not curves:
            QMessageBox.information(self, "Petrofísica", "Seleccione al menos la curva GR o la de densidad.")
            return
        self.doc.petro = p
        self.doc.add_curves(curves)
        if self.add_track.isChecked():
            self._update_results_track([c.mnemonic for c in curves])
        self.accept()

    def _update_results_track(self, names: list[str]):
        w = self.doc.well
        styles = [make_curve_style(w, m) for m in ("VSH", "PHIE", "SW") if m in names]
        track = TrackSpec(title="Resultados petrofísicos", width=220, curves=styles)
        if "VSH" in names:
            track.fills.append(FillSpec(left_value=0, right_curve="VSH", color="#a0522d", pattern="dense3",
                                        label="Vsh"))
        if "PHIE" in names:
            track.fills.append(FillSpec(left_curve="PHIE", right_value=0, color="#5dade2", pattern="solid",
                                        label="φe"))
        flags = [m for m in ("RES_FLAG", "PAY_FLAG") if m in names]
        flag_track = None
        if flags:
            flag_track = TrackSpec(title="Net res / pay", width=70, grid="none",
                                   curves=[CurveStyle(m, color=c, left=0, right=1, visible=False)
                                           for m, c in zip(flags, ("#27ae60", "#c0392b"))])
            colors = {"RES_FLAG": "#82e0aa", "PAY_FLAG": "#e74c3c"}
            for m in flags:
                flag_track.fills.append(FillSpec(left_value=0, right_curve=m, color=colors[m],
                                                 label="Reservorio" if m == "RES_FLAG" else "Pago"))
        tracks = self.doc.layout.tracks
        # Se ubican junto al track de densidad-neutrón (o el de resistividad) para que se vean de inmediato.
        anchor = next((i for i, t in enumerate(tracks) if t.title == "Densidad - Neutrón"),
                      next((i for i, t in enumerate(tracks) if t.title == "Resistividad"), len(tracks) - 1))
        for title, new in (("Resultados petrofísicos", track), ("Net res / pay", flag_track)):
            idx = next((i for i, t in enumerate(tracks) if t.title == title), None)
            if new is None:
                continue
            if idx is None:
                anchor += 1
                tracks.insert(anchor, new)
            else:
                tracks[idx] = new
                anchor = idx
        self.doc.layoutChanged.emit()


# ============================================================================ calculadora


class CalculatorDialog(QDialog):
    def __init__(self, doc: WellDocument, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle(f"Calculadora de curvas — {doc.title}")
        self.setWindowIcon(app_icon())
        self.resize(640, 440)
        lay = QHBoxLayout(self)
        left = QVBoxLayout()
        form = QFormLayout()
        self.name = QLineEdit("NUEVA")
        self.unit = QLineEdit()
        self.descr = QLineEdit()
        form.addRow("Nombre:", self.name)
        form.addRow("Unidad:", self.unit)
        form.addRow("Descripción:", self.descr)
        left.addLayout(form)
        left.addWidget(QLabel("Expresión:"))
        self.expr = QPlainTextEdit()
        self.expr.setPlaceholderText("Ej.: (2.65 - RHOB) / (2.65 - 1.0)\n     where(GR > 75, 1, 0)\n     log10(LLD)")
        left.addWidget(self.expr, 1)
        help_text = ("Operadores: + - * / ** < > <= >= == & |\n"
                     f"Funciones: {', '.join(sorted(FUNCTIONS))}\n"
                     "Constantes: pi, e, nan. Curvas con nombres especiales: [K-3104]")
        hl = QLabel(help_text)
        hl.setWordWrap(True)
        hl.setStyleSheet("color: #566573")
        left.addWidget(hl)
        self.preview = QLabel(" ")
        left.addWidget(self.preview)
        row = QHBoxLayout()
        test = QPushButton("Probar")
        test.clicked.connect(self._test)
        row.addWidget(test)
        row.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Crear curva")
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        row.addWidget(buttons)
        left.addLayout(row)
        lay.addLayout(left, 1)

        right = QVBoxLayout()
        right.addWidget(QLabel("Curvas (doble clic para insertar):"))
        self.list = QListWidget()
        for m in doc.well.curves:
            self.list.addItem(m)
        self.list.itemDoubleClicked.connect(lambda it: self.expr.insertPlainText(curve_ref(it.text())))
        right.addWidget(self.list)
        lay.addLayout(right)

    def _evaluate(self) -> np.ndarray | None:
        try:
            return evaluate(self.expr.toPlainText(), {m: c.values for m, c in self.doc.well.curves.items()})
        except CalculatorError as e:
            self.preview.setText(f"<span style='color:#c0392b'>Error: {e}</span>")
            return None

    def _test(self):
        v = self._evaluate()
        if v is not None:
            n = int(np.isfinite(v).sum())
            if n:
                self.preview.setText(f"Válida: {n} muestras · min {np.nanmin(v):.4g} · max {np.nanmax(v):.4g} · "
                                     f"media {np.nanmean(v):.4g}")
            else:
                self.preview.setText("Válida, pero el resultado no tiene valores (todo NaN)")

    def _ok(self):
        name = self.name.text().strip().upper()
        if not name or not name.replace("_", "").isalnum():
            QMessageBox.warning(self, "Calculadora", "Use un nombre con letras, números o _.")
            return
        v = self._evaluate()
        if v is None:
            return
        if name in self.doc.well.curves and self.doc.well.curves[name].formula is None:
            QMessageBox.warning(self, "Calculadora", f"{name} es una curva original del LAS; elija otro nombre.")
            return
        formula = " ".join(self.expr.toPlainText().split())
        self.doc.add_curves([Curve(name, self.unit.text().strip(), self.descr.text().strip() or "Curva calculada",
                                   v, formula=formula)])
        self.accept()


# ============================================================================ resumen por zonas


class ZoneSummaryDialog(QDialog):
    def __init__(self, doc: WellDocument, parent=None):
        super().__init__(parent)
        self.doc = doc
        w = doc.well
        p = doc.petro or petro.PetroParams()
        self.setWindowTitle(f"Resumen por zonas — {doc.title}")
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
        calc = QPushButton("Calcular")
        calc.clicked.connect(self._calc)
        row.addWidget(calc)
        lay.addLayout(row)
        self.note = QLabel()
        lay.addWidget(self.note)
        self.table = QTableWidget(0, 10)
        u = w.depth_unit
        self.table.setHorizontalHeaderLabels(["Zona", f"Tope ({u})", f"Base ({u})", f"Bruto ({u})",
                                              f"Neto res. ({u})", f"Neto pago ({u})", "N/G", "φ prom", "Sw prom",
                                              "Vsh prom"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lay.addWidget(self.table, 1)
        out = QHBoxLayout()
        copy_btn = QPushButton("Copiar (para Excel)")
        copy_btn.clicked.connect(self._copy)
        save_btn = QPushButton("Guardar CSV…")
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
                zones.insert(0, Zone("(sobre el primer tope)", w.start, first))
            return zones
        return [Zone("Pozo completo", w.start, w.stop)]

    def _calc(self):
        rows = petro.zone_summary(self.doc.well, self._zones(), self.vsh.currentData(), self.phi.currentData(),
                                  self.sw.currentData(), self.vsh_cut.value(), self.phi_cut.value(),
                                  self.sw_cut.value())
        self.note.setText("" if self.doc.well.tops else
                          "Sin topes definidos: se resume el pozo completo (Pozo ▸ Topes de formación…).")
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
        path, _ = QFileDialog.getSaveFileName(self, "Guardar resumen", f"{self.doc.title}_zonas.csv", "CSV (*.csv)")
        if path:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:  # BOM: Excel en Windows
                csv.writer(f).writerows([self._headers()] + self._rows)


def _num(v: float) -> str:
    return "—" if not np.isfinite(v) else f"{v:.3f}"


def _pct(v: float) -> str:
    return "—" if not np.isfinite(v) else f"{v * 100:.0f} %"
