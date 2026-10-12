"""Curve quality control: bad hole flags, curve editing and normalization across wells."""

import numpy as np
import pytest
from PySide6.QtCore import Qt

from innopetrol.model import petro
from innopetrol.model.mnemonics import build_triple_combo
from innopetrol.model.normalize import normalization_formula, percentiles, zone_mask
from innopetrol.model.tops import Top
from innopetrol.model.well import Curve, Well
from innopetrol.ui.document import WellDocument


def synthetic(n=200, **curves) -> Well:
    depth = np.arange(1000.0, 1000.0 + n * 0.5, 0.5)
    return Well(
        "S", None, depth, "m", curves={m: Curve(m, u, "", np.asarray(v, float)) for m, (u, v) in curves.items()}
    )


# ---------------------------------------------------------------- bad hole


def test_bad_hole_masks_porosity_and_everything_after_it():
    n = 200
    cali = np.full(n, 8.6)
    cali[50:60] = 11.0  # washout: 2.5 in over an 8.5 in bit
    drho = np.zeros(n)
    drho[100:105] = -0.3  # large density correction (absolute value counts)
    w = synthetic(
        n, RHOB=("G/C3", np.full(n, 2.32)), RT=("OHMM", np.full(n, 20.0)), CALI=("IN", cali), DRHO=("G/C3", drho)
    )
    p = petro.PetroParams(rhob_curve="RHOB", rt_curve="RT", bad_hole=True, cali_curve="CALI", drho_curve="DRHO")
    c = {x.mnemonic: x.values for x in petro.compute(w, p)}
    assert set(np.flatnonzero(c["BADHOLE"] > 0)) == set(range(50, 60)) | set(range(100, 105))
    for name in ("PHIT", "PHIE", "SW", "RES_FLAG"):
        assert np.isnan(c[name][55]) and np.isnan(c[name][102]), name
    assert c["PHIE"][0] == pytest.approx(0.2) and c["SW"][0] == pytest.approx(0.25)


def test_bad_hole_with_a_bit_size_curve_in_mm():
    n = 100
    w = synthetic(n, RHOB=("G/C3", np.full(n, 2.32)), CALI=("MM", np.full(n, 250.0)), BS=("MM", np.full(n, 216.0)))
    p = petro.PetroParams(rhob_curve="RHOB", bad_hole=True, cali_curve="CALI", bs_curve="BS", washout=1.0)
    c = {x.mnemonic: x.values for x in petro.compute(w, p)}
    assert np.all(c["BADHOLE"] == 1)  # 34 mm = 1.34 in over the bit size


def test_bad_hole_off_or_without_curves_changes_nothing(testdata_well):
    base = petro.PetroParams(gr_curve="SGR", rhob_curve="RHOB", rt_curve="LLD")
    plain = petro.build_formulas(testdata_well, base)
    flagged = petro.build_formulas(testdata_well, petro.PetroParams(**{**base.__dict__, "bad_hole": True}))
    assert [f.formula for f in plain] == [f.formula for f in flagged]  # no caliper or DRHO selected


def test_bad_hole_flag_is_shown_with_the_results(testdata_well, qtbot):
    from innopetrol.ui.petro_dialog import PetroDialog

    doc = WellDocument(testdata_well, build_triple_combo(testdata_well))
    d = PetroDialog(doc)
    qtbot.addWidget(d)
    assert d.bad_hole.isChecked() and d.cali.currentData() == "CALI" and d.drho.currentData() == "DRHO"
    d._run()
    assert "BADHOLE" in doc.well.curves
    flags = next(t for t in doc.layout.tracks if any(c.mnemonic == "BADHOLE" for c in t.curves))
    assert {c.mnemonic for c in flags.curves} >= {"RES_FLAG", "BADHOLE"}


# ---------------------------------------------------------------- curve editing


def test_curve_tools_dialog_creates_a_despiked_curve(testdata_well, qtbot):
    from innopetrol.ui.curve_tools_dialog import CurveToolsDialog

    w = testdata_well
    w.curves["SGR"].values[100] = 900.0  # a spike
    doc = WellDocument(w, build_triple_combo(w))
    d = CurveToolsDialog(doc, "SGR")
    qtbot.addWidget(d)
    assert d.formula() == "despike(SGR, 7, 3)" and d.name.text() == "SGR_DS"
    d._ok()
    new = doc.well.curves["SGR_DS"]
    assert new.values[100] < 200 and new.formula == "despike(SGR, 7, 3)"
    gr_track = next(t for t in doc.layout.tracks if any(c.mnemonic == "SGR" for c in t.curves))
    assert any(c.mnemonic == "SGR_DS" and c.style == "dash" for c in gr_track.curves)
    doc.undo_stack.undo()
    assert "SGR_DS" not in doc.well.curves


def test_curve_tools_depth_shift(testdata_well, qtbot):
    from innopetrol.ui.curve_tools_dialog import CurveToolsDialog

    doc = WellDocument(testdata_well, build_triple_combo(testdata_well))
    d = CurveToolsDialog(doc, "RHOB")
    qtbot.addWidget(d)
    d.operation.setCurrentIndex(d.operation.findData("shift"))
    d.offset.setValue(2.0)
    d.show_in_track.setChecked(False)
    d._ok()
    shifted, original = doc.well.curves["RHOB_SH"].values, doc.well.curves["RHOB"].values
    step = round(2.0 / testdata_well.step)
    assert np.allclose(shifted[step + 10 : step + 50], original[10:50], equal_nan=True)


# ---------------------------------------------------------------- normalization


def test_normalization_maps_percentiles():
    rng = np.random.default_rng(1)
    gr = rng.uniform(30, 130, 1000)
    w = synthetic(1000, GR=("GAPI", gr))
    mask = zone_mask(w, None)
    points = percentiles(gr, mask, 5, 95)
    from innopetrol.model.calculator import evaluate

    out = evaluate(normalization_formula("GR", points, (20.0, 120.0)), w.formula_env())
    assert np.percentile(out, [5, 95]) == pytest.approx([20.0, 120.0], abs=1e-6)


def test_normalize_dialog_two_wells(testdata_well, samples, qtbot, no_modal_boxes):
    from innopetrol.ui.normalize_dialog import NormalizeDialog

    other = Well.from_las(samples / "Testdata.las")
    other.name = "Hot tool"
    other.add_curve(Curve("GR", "GAPI", "", other.curves.pop("SGR").values * 1.3 + 15))  # miscalibrated
    a = WellDocument(testdata_well, build_triple_combo(testdata_well))
    b = WellDocument(other, build_triple_combo(other))
    for doc in (a, b):
        doc.well.tops = [Top("Z", 7700.0)]
    d = NormalizeDialog([a, b], a)
    qtbot.addWidget(d)
    d.zone.setCurrentIndex(d.zone.findData("Z"))
    assert d.table.rowCount() == 2 and d.table.item(1, 1).text() == "GR"
    d._apply()
    ref = percentiles(a.well.curves["SGR"].values, zone_mask(a.well, "Z"), 5, 95)
    got = percentiles(b.well.curves["GRN"].values, zone_mask(b.well, "Z"), 5, 95)
    assert got == pytest.approx(ref, rel=1e-6)  # the hot tool now reads like the reference
    assert b.undo_stack.count() == 1 and "created in" in no_modal_boxes[-1][1][2]
    assert d.wells.item(0).checkState() == Qt.CheckState.Checked
