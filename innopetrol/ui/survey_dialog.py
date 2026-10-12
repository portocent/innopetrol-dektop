"""Deviation survey and elevation of a well."""

from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QLabel, QMessageBox, QPushButton, QVBoxLayout)

from innopetrol.i18n import _
from innopetrol.model.survey import SurveyError, load_survey_csv
from innopetrol.resources import app_icon
from innopetrol.ui.document import WellDocument


class SurveyDialog(QDialog):
    def __init__(self, doc: WellDocument, parent=None):
        super().__init__(parent)
        self.doc = doc
        w = doc.well
        self.survey = w.survey
        self.setWindowTitle(_("Survey and elevation — {well}").format(well=doc.title))
        self.setWindowIcon(app_icon())
        self.resize(520, 300)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.has_elevation = QCheckBox(_("Known elevation of the depth reference (KB/DF) above sea level"))
        self.elevation = QDoubleSpinBox(decimals=2, minimum=-12000, maximum=12000)
        self.elevation.setSuffix(f" {w.depth_unit}")
        self.has_elevation.setChecked(w.elevation is not None)
        self.elevation.setValue(w.elevation or 0.0)
        self.elevation.setEnabled(w.elevation is not None)
        self.has_elevation.toggled.connect(self.elevation.setEnabled)
        form.addRow(self.has_elevation)
        form.addRow(_("Elevation:"), self.elevation)
        lay.addLayout(form)

        self.info = QLabel()
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        row = QHBoxLayout()
        load = QPushButton(_("Import survey (CSV/TXT)…"))
        load.clicked.connect(self._import)
        clear = QPushButton(_("Remove survey"))
        clear.clicked.connect(self._clear)
        row.addWidget(load)
        row.addWidget(clear)
        row.addStretch()
        lay.addLayout(row)
        hint = QLabel(_("Columns: MD, inclination and azimuth in degrees, with MD in the same unit as the log "
                        "({unit}). Headers in English or Spanish are recognized.").format(unit=w.depth_unit))
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#566573")
        lay.addWidget(hint)
        lay.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self._update_info()

    def _update_info(self):
        s, w = self.survey, self.doc.well
        if s is None:
            self.info.setText(_("No survey: the well is treated as vertical (TVD = MD)."))
            return
        td_tvd = float(s.tvd_at([w.stop])[0])
        self.info.setText(_("{count} stations · maximum inclination {inc}° · TVD at total depth {tvd} {unit} "
                            "(MD {md} {unit})").format(count=s.md.size, inc=f"{s.max_inclination:.1f}",
                                                       tvd=f"{td_tvd:.1f}", md=f"{w.stop:.1f}", unit=w.depth_unit))

    def _import(self):
        path, _filter = QFileDialog.getOpenFileName(self, _("Import survey"), "",
                                                    _("Surveys (*.csv *.txt *.dev *.svy);;All files (*)"))
        if not path:
            return
        try:
            self.survey = load_survey_csv(path)
        except (SurveyError, OSError) as e:
            QMessageBox.warning(self, _("Import survey"), str(e))
            return
        self._update_info()

    def _clear(self):
        self.survey = None
        self._update_info()

    def _ok(self):
        elevation = self.elevation.value() if self.has_elevation.isChecked() else None
        self.doc.set_survey(self.survey, elevation)
        self.accept()
