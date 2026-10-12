"""Curve display units: conversion on screen, scales follow, data untouched."""

import numpy as np
import pytest

from innopetrol.model.mnemonics import build_triple_combo
from innopetrol.ui.document import WellDocument


@pytest.fixture
def doc(testdata_well, qapp):
    return WellDocument(testdata_well, build_triple_combo(testdata_well))


def rhob_style(doc):
    return next(c for t in doc.layout.tracks for c in t.curves if c.mnemonic == "RHOB")


def test_display_conversion_keeps_data(doc):
    raw = doc.well.curves["RHOB"].values.copy()
    doc.set_curve_unit("RHOB", "kg/m3")
    shown = doc.view.curves["RHOB"]
    assert np.allclose(shown.values, raw * 1000, equal_nan=True) and shown.unit == "kg/m³"
    assert np.array_equal(doc.well.curves["RHOB"].values, raw, equal_nan=True)  # stored data untouched
    style = rhob_style(doc)
    assert (style.left, style.right, style.unit) == (1950, 2950, "kg/m3")  # the track scale followed
    doc.set_curve_unit("RHOB", None)
    style = rhob_style(doc)
    assert (style.left, style.right) == (1.95, 2.95) and "RHOB" not in doc.curve_units


def test_fill_values_follow_the_curve(doc):
    gr_track = doc.layout.tracks[0]
    doc.set_curve_unit("TNPH", "%")
    dn = next(t for t in doc.layout.tracks if any(c.mnemonic == "TNPH" for c in t.curves))
    tnph = next(c for c in dn.curves if c.mnemonic == "TNPH")
    assert (tnph.left, tnph.right) == (45, -15)
    assert gr_track.fills[0].right_value == 75  # untouched: GR has no conversion


def test_unit_system(doc):
    doc.apply_unit_system("metric")
    assert doc.curve_units["RHOB"] == "kg/m3" and doc.curve_units["DTLN"] == "us/m" and doc.curve_units["CALI"] == "mm"
    assert doc.view.depth_unit == "m" and "SGR" not in doc.curve_units  # gAPI has no metric alternative
    assert doc.view.value_at("RHOB", doc.view.to_display(8000)) == pytest.approx(doc.well.value_at("RHOB", 8000) * 1000)
    doc.apply_unit_system("file")
    assert doc.curve_units == {} and doc.view.depth_unit == "ft"
    assert rhob_style(doc).left == 1.95


def test_adopt_layout_converts_template_scales(doc):
    from innopetrol.model.layout import CurveStyle, LogLayout, TrackSpec

    doc.set_curve_unit("RHOB", "kg/m3")
    layout = LogLayout([TrackSpec(curves=[CurveStyle("RHOB", left=1.95, right=2.95, unit="g/cm3")])])
    doc.adopt_layout(layout)
    c = layout.tracks[0].curves[0]
    assert (c.left, c.right, c.unit) == (1950, 2950, "kg/m3")


def test_density_in_kg_gets_a_sensible_default_scale(doc):
    from innopetrol.model.well import Curve

    doc.well.add_curve(Curve("RHOB", "KG/M3", "", doc.well.curves["RHOB"].values * 1000))
    style = doc.style_for("RHOB")
    assert (style.left, style.right) == (1950, 2950)


@pytest.fixture
def win(qtbot, tmp_path, samples):
    from PySide6.QtCore import QSettings

    from innopetrol.ui.main_window import MainWindow

    w = MainWindow(QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat))
    qtbot.addWidget(w)
    w.show()
    w.open_las([str(samples / "Testdata.las")])
    yield w
    w.dirty = False
    for v in w.views.values():
        v.confirm_close = False


def test_unit_system_menu_applies_to_open_and_new_wells(win, samples):
    win.set_unit_system("metric")
    assert win.docs[0].curve_units["RHOB"] == "kg/m3" and win.docs[0].view.depth_unit == "m"
    win.open_las([str(samples / "TotalDepthPrueba.las")])
    new = win.docs[-1]
    assert new.curve_units.get("RHOB") == "kg/m3"
    style = next(c for t in new.layout.tracks for c in t.curves if c.mnemonic == "RHOB")
    assert (style.left, style.right) == (1950, 2950)
    assert "kg/m³" in win.views[new].canvas.well.curves["RHOB"].unit


def test_curve_unit_from_tree_and_project_round_trip(win, tmp_path):
    doc = win.docs[0]
    win.set_curve_unit(doc, "DTLN", "us/m")
    assert doc.view.curves["DTLN"].unit == "µs/m"
    win.project_path = tmp_path / "p.ipproj"
    assert win.save_project()
    win.dirty = False
    win.open_project(str(tmp_path / "p.ipproj"))
    reopened = win.docs[0]
    assert reopened.curve_units == {"DTLN": "us/m"}
    style = next(c for t in reopened.layout.tracks for c in t.curves if c.mnemonic == "DTLN")
    assert style.left == pytest.approx(140 / 0.3048, rel=1e-4)  # scale stayed in µs/m


def test_template_from_metric_well_on_oilfield_well(win, samples, tmp_path):
    from innopetrol.model.template import load_template, save_template

    metric = win.docs[0]
    metric.set_curve_unit("RHOB", "kg/m3")
    save_template(tmp_path / "t.ipt.json", metric.layout)
    win.open_las([str(samples / "TotalDepthPrueba.las")])
    other = win.docs[-1]
    win._apply_layout(other, load_template(tmp_path / "t.ipt.json"))
    style = next(c for t in other.layout.tracks for c in t.curves if c.mnemonic == "RHOB")
    assert (style.left, style.right) == (1.95, 2.95)  # converted back to the well's g/cm³
