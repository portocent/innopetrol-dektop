"""Petrophysics dialog: zones table, shaly-sand model, temperature and graphical pickers."""

import numpy as np
import pytest
from PySide6.QtCore import QPointF, Qt

from innopetrol.model.mnemonics import build_triple_combo
from innopetrol.model.tops import Top
from innopetrol.ui.document import WellDocument


@pytest.fixture
def doc(testdata_well, qapp):
    testdata_well.tops = [Top("A", 7790), Top("B", 8040)]
    return WellDocument(testdata_well, build_triple_combo(testdata_well))


@pytest.fixture
def dialog(doc, qtbot):
    from innopetrol.ui.petro_dialog import PetroDialog

    d = PetroDialog(doc)
    qtbot.addWidget(d)
    return d


def zone_cell(dialog, zone_row, key):
    return dialog._zone_cell(zone_row, key)


def test_first_time_guesses(dialog, doc):
    p = dialog.params()
    assert p.gr_curve == "SGR" and p.rt_curve == "LLD" and p.rsh > 0
    assert p.temp_unit == "degF" and p.gradient == 1.5  # well in feet
    assert dialog.zone_table.rowCount() == 2 and p.zones == {}


def test_zone_values_are_used(dialog, doc):
    zone_cell(dialog, 1, "rw").setText("0,02")  # decimal comma accepted
    zone_cell(dialog, 1, "phi_cut").setText("0.12")
    dialog.sw_model.setCurrentIndex(dialog.sw_model.findData("indonesia"))
    dialog._run()
    assert doc.petro.zones == {"B": {"rw": 0.02, "phi_cut": 0.12}}
    sw = doc.well.curves["SW"]
    assert "Indonesia" in sw.description and "where((DEPTH >= 8040), 0.02" in sw.formula
    assert doc.undo_stack.count() == 1
    reopened = type(dialog)(doc)
    assert zone_cell(reopened, 1, "rw").text() == "0.02"
    reopened.deleteLater()


def test_invalid_zone_value_is_reported(dialog, doc, no_modal_boxes):
    zone_cell(dialog, 0, "m").setText("two")
    dialog._run()
    assert "SW" not in doc.well.curves
    assert no_modal_boxes and "is not a number" in no_modal_boxes[-1][1][2]


def test_zone_check_finds_bad_gr(dialog, doc, no_modal_boxes):
    zone_cell(dialog, 0, "gr_clean").setText("500")
    dialog._run()
    assert "VSH" not in doc.well.curves and "(zone A)" in no_modal_boxes[-1][1][2]


def test_temperature_unit_change_converts_values(dialog):
    dialog.temp_mode.setCurrentIndex(dialog.temp_mode.findData("gradient"))
    assert dialog.gradient.isEnabled() and not dialog.temp_curve.isEnabled()
    dialog.temp_unit.setCurrentIndex(dialog.temp_unit.findData("degC"))
    assert dialog.surface_temp.value() == pytest.approx(15.6, abs=0.05)  # 60 °F
    assert dialog.gradient.value() == pytest.approx(0.83, abs=0.01)  # 1.5 °F/100 ft
    dialog._run()
    assert "TFORM" in dialog.doc.well.curves and "RWT" in dialog.doc.well.curves


def test_gr_picker_lines_follow_the_mouse(qtbot):
    from innopetrol.ui.pickers import GrPickerDialog

    values = np.concatenate([np.random.default_rng(1).normal(30, 5, 500), np.random.default_rng(2).normal(110, 8, 500)])
    d = GrPickerDialog(values, 40, 100, "GR (API)", "test")
    qtbot.addWidget(d)
    d.show()
    qtbot.waitExposed(d)
    r, xa = d.hist.plot_area, d.hist.x_axis
    x = r.left() + float(xa.map(np.array([130.0]), r.width())[0])
    qtbot.mouseClick(d.hist, Qt.LeftButton, pos=QPointF(x, r.center().y()).toPoint())
    assert d.shale.value() == pytest.approx(130, abs=1.5)  # nearest line moved to the click
    assert d.clean.value() == 40
    d._percentiles()
    low, high = d.result_values()
    assert low < 40 and high > 100


def test_pickett_fit_and_drag(qtbot):
    from innopetrol.ui.pickers import PickettPicker

    rng = np.random.default_rng(3)
    phi = rng.uniform(0.08, 0.3, 400)
    rt = 0.08 / phi**2  # water-bearing: on the Sw = 1 line of Rw = 0.08
    rt[200:] *= rng.uniform(5, 30, 200)  # hydrocarbon-bearing: higher resistivity
    plot = PickettPicker(rt, phi)
    qtbot.addWidget(plot)
    assert plot.fit_water_line() == pytest.approx(0.08, rel=0.01)
    plot.resize(600, 500)
    plot.show()
    qtbot.waitExposed(plot)
    r = plot.plot_area
    pos = QPointF(r.left() + r.width() * 0.5, r.top() + r.height() * 0.4)
    got = []
    plot.rwChanged.connect(got.append)
    qtbot.mousePress(plot, Qt.LeftButton, pos=pos.toPoint())
    rt_here = plot.xa.value_at(pos.toPoint().x() - r.left(), r.width())
    phi_here = plot.ya.value_at(r.bottom() - pos.toPoint().y(), r.height())
    assert got and got[-1] == pytest.approx(rt_here * phi_here**2, rel=1e-3)


def test_zone_summary_uses_zone_cutoffs(dialog, doc, qtbot):
    from innopetrol.ui.zone_summary_dialog import ZoneSummaryDialog

    zone_cell(dialog, 1, "phi_cut").setText("0.9")
    dialog._run()
    z = ZoneSummaryDialog(doc)
    qtbot.addWidget(z)
    row_b = next(r for r in z._rows if r[0] == "B")
    assert float(row_b[4]) == 0  # net reservoir: nothing passes φ ≥ 0.9
    assert "B" in z.note.text()
