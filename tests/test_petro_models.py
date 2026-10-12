"""Shaly-sand models, parameters by zone and Rw corrected for temperature."""

import numpy as np
import pytest

from innopetrol.model import petro
from innopetrol.model.project import WellEntry, load_project, save_project
from innopetrol.model.mnemonics import build_triple_combo
from innopetrol.model.survey import Survey
from innopetrol.model.tops import Top, zones_from_tops

BASE = dict(gr_curve="SGR", gr_clean=20, gr_shale=130, rhob_curve="RHOB", rt_curve="LLD")


def computed(well, **kw):
    return {c.mnemonic: c for c in petro.compute(well, petro.PetroParams(**{**BASE, **kw}))}


def test_shaly_sand_models_reduce_to_archie_without_shale():
    rt, phi = np.array([2.0, 10.0, 50.0]), np.array([0.25, 0.18, 0.12])
    archie = petro.sw_archie(rt, phi, 0.05)
    assert np.allclose(petro.sw_simandoux(rt, phi, 0.0, 0.05, 3.0), archie)
    assert np.allclose(petro.sw_indonesia(rt, phi, 0.0, 0.05, 3.0), archie)
    # Shale conductivity explains part of the low resistivity: less water than Archie says.
    assert np.all(petro.sw_simandoux(rt, phi, 0.3, 0.05, 3.0) < archie)
    assert np.all(petro.sw_indonesia(rt, phi, 0.3, 0.05, 3.0) < archie)


@pytest.mark.parametrize("model", ["simandoux", "indonesia"])
def test_shaly_sand_formulas_match_the_reference(testdata_well, model):
    w = testdata_well
    c = computed(w, sw_model=model, rsh=4.0, rw=0.04)
    rt, phie, vsh = w.curves["LLD"].values, c["PHIE"].values, c["VSH"].values
    ref = (petro.sw_simandoux(rt, phie, vsh, 0.04, 4.0) if model == "simandoux"
           else petro.sw_indonesia(rt, phie, vsh, 0.04, 4.0))
    ok = np.isfinite(ref)
    assert ok.sum() > 1000
    assert np.allclose(c["SW"].values[ok], ref[ok])
    assert model.capitalize() in c["SW"].description


def test_shaly_sand_model_needs_vsh(testdata_well):
    c = computed(testdata_well, gr_curve=None, sw_model="simandoux")
    assert "Archie" in c["SW"].description


def test_parameters_by_zone(testdata_well):
    w = testdata_well
    w.tops = [Top("A", 7700), Top("B", 8000)]
    c = computed(w, rw=0.05, zones={"B": {"rw": 0.02, "gr_shale": 110}, "A": {"rw": 0.05}})
    assert "where((DEPTH >= 8000), 0.02, 0.05)" in c["SW"].formula  # A equals the default: not written
    rt, phie = w.curves["LLD"].values, c["PHIE"].values
    rw = np.where(w.depth >= 8000, 0.02, 0.05)
    ref = petro.sw_archie(rt, phie, rw)
    ok = np.isfinite(ref)
    assert np.allclose(c["SW"].values[ok], ref[ok])
    igr = np.clip((w.curves["SGR"].values - 20) / (np.where(w.depth >= 8000, 110, 130) - 20), 0, 1)
    assert np.allclose(c["VSH"].values, igr, equal_nan=True)


def test_zone_cutoffs_in_the_summary(testdata_well):
    w = testdata_well
    for curve in computed(w).values():
        w.add_curve(curve)
    zones = zones_from_tops([Top("A", 7700), Top("B", 8000)], w.stop)
    plain = petro.zone_summary(w, zones, "VSH", "PHIE", "SW", 0.4, 0.08, 0.6)
    strict = petro.zone_summary(w, zones, "VSH", "PHIE", "SW", 0.4, 0.08, 0.6, {"B": {"phi_cut": 0.5}})
    assert strict[0].net_reservoir == plain[0].net_reservoir
    assert strict[1].net_reservoir == 0 < plain[1].net_reservoir


def test_arps_known_value():
    # Rw 0.1 ohm·m at 25 °C is 0.0482 ohm·m at 75 °C; the same in °F.
    assert petro.rw_at_temperature(0.1, 25, 75) == pytest.approx(0.1 * 46.5 / 96.5)
    assert petro.rw_at_temperature(0.1, 77, 167, "degF") == pytest.approx(0.0482, abs=2e-4)


def test_rw_from_geothermal_gradient_uses_tvd(testdata_well):
    w = testdata_well  # depths in feet
    w.survey = Survey(np.array([0.0, 7000, 9000]), np.array([0.0, 30, 30]), np.array([0.0, 90, 90]))
    c = computed(w, temp_mode="gradient", temp_unit="degF", surface_temp=60, gradient=1.5, rw=0.05,
                 rw_temp=75)
    temp = 60 + 1.5 * w.tvd() / 100
    assert np.allclose(c["TFORM"].values, temp)
    assert c["TFORM"].values[-1] < 60 + 1.5 * w.depth[-1] / 100  # deviated: TVD < MD
    assert np.allclose(c["RWT"].values, petro.rw_at_temperature(0.05, 75, temp, "degF"))
    ref = petro.sw_archie(w.curves["LLD"].values, c["PHIE"].values, c["RWT"].values)
    ok = np.isfinite(ref)
    assert np.allclose(c["SW"].values[ok], ref[ok])


def test_temperature_curve_in_another_unit(testdata_well):
    w = testdata_well
    from innopetrol.model.well import Curve

    w.add_curve(Curve("BHT", "DEGC", "", np.full_like(w.depth, 80.0)))
    c = computed(w, temp_mode="curve", temp_curve="BHT", temp_unit="degF", rw_temp=77, rw=0.1)
    # 80 °C = 176 °F, converted inside the formula.
    assert np.allclose(c["RWT"].values, petro.rw_at_temperature(0.1, 77, 176, "degF"))


def test_project_keeps_zone_parameters_and_recomputes_with_tvd(testdata_well, tmp_path):
    w = testdata_well
    w.tops = [Top("A", 7700)]
    w.survey = Survey(np.array([0.0, 7000, 9000]), np.array([0.0, 20, 20]), np.array([0.0, 0, 0]))
    params = petro.PetroParams(**BASE, temp_mode="gradient", zones={"A": {"rw": 0.03, "m": 1.8}})
    for curve in petro.compute(w, params):
        w.add_curve(curve)
    save_project(tmp_path / "p.ipproj", [WellEntry(w, build_triple_combo(w), params)])
    res = load_project(tmp_path / "p.ipproj")
    assert not res.errors
    e = res.entries[0]
    assert e.petro == params and e.petro.value("rw", "A") == 0.03 and e.petro.value("rw", "X") == 0.05
    assert np.allclose(e.well.curves["TFORM"].values, w.curves["TFORM"].values)
    assert np.allclose(e.well.curves["SW"].values, w.curves["SW"].values, equal_nan=True)
