"""Deviation survey, elevation and surface location of a well."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from innopetrol.i18n import _
from innopetrol.model.location import Location, parse_coordinate
from innopetrol.model.survey import SurveyError, load_survey_csv
from innopetrol.resources import app_icon
from innopetrol.ui.document import WellDocument


class SurveyDialog(QDialog):
    def __init__(self, doc: WellDocument, parent=None):
        super().__init__(parent)
        self.doc = doc
        w = doc.well
        self.survey = w.survey
        self.setWindowTitle(_("Survey, elevation and location — {well}").format(well=doc.title))
        self.setWindowIcon(app_icon())
        self.resize(560, 420)
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
        hint = QLabel(
            _(
                "Columns: MD, inclination and azimuth in degrees, with MD in the same unit as the log "
                "({unit}). Headers in English or Spanish are recognized."
            ).format(unit=w.depth_unit)
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#566573")
        lay.addWidget(hint)

        lay.addWidget(self._build_location(w.location))
        lay.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self._update_info()

    def _build_location(self, loc: Location | None) -> QGroupBox:
        """Surface location, for the base map: latitude/longitude or projected X/Y."""
        box = QGroupBox(_("Surface location"))
        box.setCheckable(True)
        box.setChecked(loc is not None)
        f = QFormLayout(box)
        self.location_box = box
        self.coord_kind = QComboBox()
        self.coord_kind.addItem(_("Latitude / longitude (degrees)"), "geo")
        self.coord_kind.addItem(_("Projected X / Y (meters)"), "m")
        self.coord_kind.addItem(_("Projected X / Y (feet)"), "ft")
        kind = "geo" if loc is None or loc.geographic else loc.unit
        self.coord_kind.setCurrentIndex(max(self.coord_kind.findData(kind), 0))
        self.coord_y = QLineEdit("" if loc is None else f"{loc.y:.10g}")
        self.coord_x = QLineEdit("" if loc is None else f"{loc.x:.10g}")
        self.y_label, self.x_label = QLabel(), QLabel()
        f.addRow(_("Coordinates:"), self.coord_kind)
        f.addRow(self.y_label, self.coord_y)
        f.addRow(self.x_label, self.coord_x)
        self.coord_kind.currentIndexChanged.connect(self._coord_labels)
        self._coord_labels()
        return box

    def _update_info(self):
        s, w = self.survey, self.doc.well
        if s is None:
            self.info.setText(_("No survey: the well is treated as vertical (TVD = MD)."))
            return
        td_tvd = float(s.tvd_at([w.stop])[0])
        self.info.setText(
            _(
                "{count} stations · maximum inclination {inc}° · TVD at total depth {tvd} {unit} (MD {md} {unit})"
            ).format(
                count=s.md.size,
                inc=f"{s.max_inclination:.1f}",
                tvd=f"{td_tvd:.1f}",
                md=f"{w.stop:.1f}",
                unit=w.depth_unit,
            )
        )

    def _import(self):
        path, _filter = QFileDialog.getOpenFileName(
            self, _("Import survey"), "", _("Surveys (*.csv *.txt *.dev *.svy);;All files (*)")
        )
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

    def _coord_labels(self):
        geo = self.coord_kind.currentData() == "geo"
        self.y_label.setText(_("Latitude:") if geo else _("Y (northing):"))
        self.x_label.setText(_("Longitude:") if geo else _("X (easting):"))
        for edit in (self.coord_x, self.coord_y):
            edit.setPlaceholderText(_("e.g. 58° 26' 29.9\" N or -58.4416") if geo else _("e.g. 435050.2"))

    def location(self) -> Location | None:
        """Location typed in the dialog. Raises ValueError with a message if it is not valid."""
        if not self.location_box.isChecked():
            return None
        kind = self.coord_kind.currentData()
        x, y = parse_coordinate(self.coord_x.text()), parse_coordinate(self.coord_y.text())
        if x is None or y is None:
            raise ValueError(_("Enter both coordinates of the surface location."))
        if kind == "geo":
            if abs(y) > 90 or abs(x) > 180:
                raise ValueError(_("Latitude must be between -90 and 90 and longitude between -180 and 180."))
            return Location(x, y, geographic=True)
        return Location(x, y, geographic=False, unit=kind)

    def _ok(self):
        try:
            location = self.location()
        except ValueError as e:
            QMessageBox.warning(self, self.windowTitle(), str(e))
            return
        elevation = self.elevation.value() if self.has_elevation.isChecked() else None
        self.doc.set_survey(self.survey, elevation, location)
        self.accept()
