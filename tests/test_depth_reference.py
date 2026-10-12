"""Depth reference (MD/TVD/TVDSS), display unit and surveys in the interface."""

import numpy as np
import pytest
from PySide6.QtCore import QSettings

from innopetrol.model import dlis
from innopetrol.model.depth_view import DepthView
from innopetrol.model.survey import Survey
from innopetrol.model.tops import Top
from innopetrol.ui.main_window import MainWindow


@pytest.fixture
def win(qtbot, tmp_path, samples):
    w = MainWindow(QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    qtbot.addWidget(w)
    w.resize(1300, 850)
    w.show()
    w.open_las([str(samples / "Testdata.las")])
    yield w
    w.dirty = False


def slant_survey():
    # Vertical to 7000 ft, then 60° — TVD below 7000 grows at cos(60°) = 0.5 per foot of MD.
    return Survey(np.array([0, 7000, 7001, 9000]), np.array([0, 0, 60, 60]), np.array([0, 0, 90, 90]))


def test_depth_view_conversions(testdata_well):
    w = testdata_well
    w.survey, w.elevation = slant_survey(), 100.0
    tvd = DepthView(w, "tvd")
    assert tvd.to_display(8000) == pytest.approx(7000 + 1000 * 0.5, abs=1)
    assert tvd.to_md(tvd.to_display(8000)) == pytest.approx(8000, abs=1e-6)
    tvdss = DepthView(w, "tvdss")
    assert tvdss.to_display(8000) == pytest.approx(7500 - 100, abs=1)
    meters = DepthView(w, "md", "m")
    assert meters.depth_unit == "m" and meters.to_display(1000) == pytest.approx(304.8)
    w.tops = [Top("A", 8000)]
    assert tvd.tops[0].depth == pytest.approx(7500, abs=1) and w.tops[0].depth == 8000  # stored in MD


def test_tvdss_without_elevation_falls_back_to_tvd(testdata_well):
    testdata_well.elevation = None
    assert DepthView(testdata_well, "tvdss").reference == "tvd"


def test_reference_switch_in_window(win):
    doc = win.docs[0]
    c = win.views[doc].canvas
    assert not win.reference_actions["tvdss"].isEnabled() or doc.well.elevation is not None
    doc.set_survey(slant_survey(), 50.0)
    win.activate_doc(doc)
    c.set_scale(500)
    c.center_on(8000)
    win.set_depth_reference("tvd")
    assert doc.view.reference == "tvd" and c.well.depth_mnemonic == "TVD"
    assert c.current_scale() == pytest.approx(500)  # same scale after the switch
    center_md = float(doc.view.to_md(c.depth_at(c.header_h + c.body_h / 2)))
    assert center_md == pytest.approx(8000, abs=2)  # same place in the well
    assert "TVD" in c.readout(8000) and "TVDSS" in c.readout(8000)
    win.set_depth_reference("tvdss")
    assert doc.view.reference == "tvdss"
    win.set_display_unit("m")
    assert c.well.depth_unit == "m" and c.current_scale() == pytest.approx(500)


def test_top_added_on_tvd_view_is_stored_in_md(win, monkeypatch):
    from innopetrol.ui import well_view

    doc = win.docs[0]
    doc.set_survey(slant_survey(), None)
    doc.set_depth_reference("tvd")
    monkeypatch.setattr(well_view.QInputDialog, "getText", staticmethod(lambda *a, **k: ("T1", True)))
    win.views[doc].add_top_at(7500.0)  # picked at TVD 7500 (≈ MD 7999)
    md = doc.well.tops[0].depth
    assert md == pytest.approx(7999.35, abs=0.05)  # stored in MD…
    assert float(doc.well.survey.tvd_at([md])[0]) == pytest.approx(7500, abs=0.05)  # …at the picked TVD


def test_project_keeps_survey_and_reference(win, tmp_path):
    doc = win.docs[0]
    doc.set_survey(slant_survey(), 75.0)
    doc.set_depth_reference("tvdss")
    doc.set_display_unit("m")
    win.project_path = tmp_path / "p.ipproj"
    assert win.save_project()
    win.dirty = False
    win.open_project(str(tmp_path / "p.ipproj"))
    d = win.docs[0]
    assert d.well.survey is not None and d.well.elevation == 75.0
    assert d.depth_reference == "tvdss" and d.display_unit == "m"


@pytest.mark.skipif(not dlis.available(), reason="dlisio not installed")
def test_open_dlis_from_window(win, tmp_path):
    from dliswriter import DLISFile, enums

    df = DLISFile()
    lf = df.add_logical_file()
    lf.add_origin("O", well_name="D-1")
    ch_d = lf.add_channel("DEPT", data=1000 + np.arange(100) * 0.5, units=enums.Unit.METER)
    ch_g = lf.add_channel("GR", data=np.linspace(20, 120, 100), units="gAPI")
    lf.add_frame("MAIN", channels=(ch_d, ch_g), index_type=enums.FrameIndexType.BOREHOLE_DEPTH)
    path = tmp_path / "d.dlis"
    df.write(str(path))
    win.open_las([str(path)])
    doc = win.docs[-1]
    assert doc.title == "D-1" and doc.well.source == "MAIN" and "GR" in doc.well.curves
    win.project_path = tmp_path / "p.ipproj"
    assert win.save_project()
    win.dirty = False
    win.open_project(str(tmp_path / "p.ipproj"))
    assert [d.title for d in win.docs] == ["Test Well 1", "D-1"]
