"""Zone summary: gross, net reservoir and net pay thickness and averages per zone."""

from __future__ import annotations

import csv

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from innopetrol.i18n import _
from innopetrol.model import petro
from innopetrol.model.mnemonics import find_curve
from innopetrol.model.tops import Zone, zones_from_tops
from innopetrol.model.workbook import write_table
from innopetrol.resources import app_icon
from innopetrol.ui.document import WellDocument
from innopetrol.ui.widgets import curve_combo, spin


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
        self.vsh = curve_combo(doc.well, "VSH" if "VSH" in w.curves else find_curve(w, "vsh"))
        self.phi = curve_combo(doc.well, "PHIE" if "PHIE" in w.curves else find_curve(w, "effective_porosity"))
        self.sw = curve_combo(doc.well, "SW" if "SW" in w.curves else find_curve(w, "sw"))
        self.vsh_cut = spin(p.vsh_cut, 0, 1)
        self.phi_cut = spin(p.phi_cut, 0, 1)
        self.sw_cut = spin(p.sw_cut, 0, 1)
        for lbl, wdg in (
            ("Vsh", self.vsh),
            ("≤", self.vsh_cut),
            ("φ", self.phi),
            ("≥", self.phi_cut),
            ("Sw", self.sw),
            ("≤", self.sw_cut),
        ):
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
        self.table.setHorizontalHeaderLabels(
            [
                _("Zone"),
                _("Top ({unit})").format(unit=u),
                _("Base ({unit})").format(unit=u),
                _("Gross ({unit})").format(unit=u),
                _("Net res. ({unit})").format(unit=u),
                _("Net pay ({unit})").format(unit=u),
                "N/G",
                _("Avg φ"),
                _("Avg Sw"),
                _("Avg Vsh"),
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # zone names
        lay.addWidget(self.table, 1)
        out = QHBoxLayout()
        copy_btn = QPushButton(_("Copy (for Excel)"))
        copy_btn.clicked.connect(self._copy)
        save_btn = QPushButton(_("Save CSV…"))
        save_btn.clicked.connect(self._save)
        xlsx_btn = QPushButton(_("Save Excel…"))
        xlsx_btn.clicked.connect(self._save_xlsx)
        out.addWidget(copy_btn)
        out.addWidget(save_btn)
        out.addWidget(xlsx_btn)
        out.addStretch()
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
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
            cutoffs = {
                z: {k: v for k, v in vals.items() if k in ("vsh_cut", "phi_cut", "sw_cut")}
                for z, vals in self.doc.petro.zones.items()
            }
            cutoffs = {z: v for z, v in cutoffs.items() if v}
        rows = petro.zone_summary(
            self.doc.well,
            self._zones(),
            self.vsh.currentData(),
            self.phi.currentData(),
            self.sw.currentData(),
            self.vsh_cut.value(),
            self.phi_cut.value(),
            self.sw_cut.value(),
            cutoffs,
        )
        notes = []
        if not self.doc.well.tops:
            notes.append(_("No tops defined: the whole well is summarized (Well ▸ Formation tops…)."))
        used = [r.zone for r in rows if r.zone in cutoffs]
        if used:
            notes.append(
                _("Zones with their own cutoffs (from Petrophysics ▸ Parameters by zone): {zones}").format(
                    zones=", ".join(used)
                )
            )
        self.note.setText("\n".join(notes))
        self._rows = []
        self._summary = rows
        self.table.setRowCount(len(rows))
        for r, z in enumerate(rows):
            vals = [
                z.zone,
                f"{z.top:.1f}",
                f"{z.base:.1f}",
                f"{z.gross:.1f}",
                f"{z.net_reservoir:.1f}",
                f"{z.net_pay:.1f}",
                _pct(z.ntg),
                _num(z.phi_avg),
                _num(z.sw_avg),
                _num(z.vsh_avg),
            ]
            self._rows.append(vals)
            for c, v in enumerate(vals):
                item = QTableWidgetItem(v)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    if c
                    else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
                self.table.setItem(r, c, item)

    def _headers(self):
        return [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]

    def _copy(self):
        text = "\n".join("\t".join(r) for r in [self._headers(), *self._rows])
        QGuiApplication.clipboard().setText(text)

    def _save(self):
        path, _filter = QFileDialog.getSaveFileName(
            self, _("Save summary"), f"{self.doc.title}_zones.csv", "CSV (*.csv)"
        )
        if path:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:  # BOM: Excel on Windows
                csv.writer(f).writerows([self._headers(), *self._rows])

    def _save_xlsx(self):
        """Excel file with numbers (not text), so the summary can be used in calculations."""
        path, _filter = QFileDialog.getSaveFileName(
            self, _("Save summary"), f"{self.doc.title}_zones.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        rows = [
            [z.zone, z.top, z.base, z.gross, z.net_reservoir, z.net_pay, z.ntg, z.phi_avg, z.sw_avg, z.vsh_avg]
            for z in self._summary
        ]
        try:
            write_table(path, _("Zone summary"), self._headers(), rows)
        except OSError as e:
            QMessageBox.warning(self, _("Save summary"), _("Could not save: {error}").format(error=e))


def _num(v: float) -> str:
    return "—" if not np.isfinite(v) else f"{v:.3f}"


def _pct(v: float) -> str:
    return "—" if not np.isfinite(v) else f"{v * 100:.0f} %"
