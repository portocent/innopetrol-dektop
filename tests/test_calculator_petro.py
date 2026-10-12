import numpy as np
import pytest

from innopetrol.model import petro
from innopetrol.model.calculator import CalculatorError, evaluate
from innopetrol.model.tops import Top, load_tops_csv, save_tops_csv, zones_from_tops

C = {"RHOB": np.array([2.65, 2.4, 2.15, np.nan]), "K-1": np.array([1.0, 10, 100, 1000])}


def test_calculator_basic():
    out = evaluate("(2.65 - RHOB) / (2.65 - 1.0)", C)
    assert np.allclose(out[:3], [0, 0.25 / 1.65, 0.5 / 1.65]) and np.isnan(out[3])
    assert np.allclose(evaluate("log10([K-1])", C), [0, 1, 2, 3])
    assert np.allclose(evaluate('where(curve("K-1") > 50, 1, 0)', C), [0, 0, 1, 1])
    assert np.allclose(evaluate("clip(RHOB, 2.2, 2.5)", C)[:3], [2.5, 2.4, 2.2])


@pytest.mark.parametrize("expr", [
    "__import__('os').system('echo hacked')",
    "RHOB.__class__",
    "[x for x in RHOB]",
    "lambda: 1",
    "open('/etc/passwd')",
    "RHOB[0]",
    "'texto'",
    "FOO + 1",
])
def test_calculator_rejects_unsafe(expr):
    with pytest.raises(CalculatorError):
        evaluate(expr, C)


def test_reference_functions():
    assert petro.phi_density(2.4, 2.65, 1.0) == pytest.approx(0.25 / 1.65)
    assert petro.vsh_larionov_tertiary(1.0) == pytest.approx(0.083 * (2 ** 3.7 - 1))
    assert petro.vsh_larionov_older(0.5) == pytest.approx(0.33)
    # Archie: Rw=0.05, φ=0.2, Rt=20 → Sw = sqrt(0.05/(0.04*20)) = 0.25
    assert petro.sw_archie(20, 0.2, 0.05) == pytest.approx(0.25)


def test_compute_matches_reference(testdata_well):
    w = testdata_well
    p = petro.PetroParams(gr_curve="SGR", gr_clean=20, gr_shale=130, vsh_method="larionov_tertiary",
                          rhob_curve="RHOB", nphi_curve="TNPH", phi_method="nd_average", rt_curve="LLD")
    curves = {c.mnemonic: c for c in petro.compute(w, p)}
    assert list(curves) == ["VSH", "PHID", "PHIT", "PHIE", "SW", "VMAT", "BVW", "BVH", "RES_FLAG", "PAY_FLAG"]
    igr = petro.gr_index(w.curves["SGR"].values, 20, 130)
    assert np.allclose(curves["VSH"].values, np.clip(petro.vsh_larionov_tertiary(igr), 0, 1), equal_nan=True)
    phit = np.clip((np.clip(petro.phi_density(w.curves["RHOB"].values), -0.15, 0.6) + w.curves["TNPH"].values) / 2, 0, 0.6)
    phie = np.clip(phit * (1 - curves["VSH"].values), 0, 0.6)
    assert np.allclose(curves["PHIE"].values, phie, equal_nan=True)
    sw = petro.sw_archie(w.curves["LLD"].values, phie, 0.05)
    ok = np.isfinite(sw) & np.isfinite(curves["SW"].values)
    assert ok.sum() > 1000
    assert np.allclose(curves["SW"].values[ok], sw[ok])
    assert set(np.unique(curves["PAY_FLAG"].values[np.isfinite(curves["PAY_FLAG"].values)])) <= {0, 1}
    assert all(c.formula for c in curves.values())


def test_zone_summary(testdata_well):
    w = testdata_well
    for c in petro.compute(w, petro.PetroParams(gr_curve="SGR", rhob_curve="RHOB", rt_curve="LLD")):
        w.add_curve(c)
    zones = zones_from_tops([Top("A", 7700), Top("B", 8000)], w.stop)
    rows = petro.zone_summary(w, zones, "VSH", "PHIE", "SW", 0.4, 0.08, 0.6)
    assert [r.zone for r in rows] == ["A", "B"]
    assert rows[0].gross == pytest.approx(300, abs=1)
    for r in rows:
        assert 0 <= r.net_pay <= r.net_reservoir <= r.gross
        assert 0 <= r.ntg <= 1


def test_tops_csv(tmp_path):
    p = tmp_path / "tops.csv"
    p.write_text("Pozo;Tope;Profundidad\nW1;Arena C;7800,5\nW2;Otro;1\nW1;Arena B;7700\n", encoding="utf-8")
    tops = load_tops_csv(p, well_name="w1")
    assert [(t.name, t.depth) for t in tops] == [("Arena B", 7700), ("Arena C", 7800.5)]
    save_tops_csv(tmp_path / "o.csv", tops)
    again = load_tops_csv(tmp_path / "o.csv")
    assert [(t.name, t.depth, t.color) for t in again] == [(t.name, t.depth, t.color) for t in tops]
    p.write_text("Top A,100\nTop B,200,#00ff00\n")
    tops = load_tops_csv(p)
    assert tops[1].color == "#00ff00" and tops[0].depth == 100


def test_results_do_not_depend_on_input_units(testdata_well):
    """Density in kg/m³ and neutron in % give the same results as g/cm³ and fraction."""
    from innopetrol.model.well import Curve

    w = testdata_well
    p = petro.PetroParams(gr_curve="SGR", rhob_curve="RHOB", nphi_curve="TNPH", phi_method="nd_average",
                          rt_curve="LLD")
    reference = {c.mnemonic: c.values for c in petro.compute(w, p)}
    w.add_curve(Curve("RHOB", "KG/M3", "", w.curves["RHOB"].values * 1000))
    w.add_curve(Curve("TNPH", "PU", "", w.curves["TNPH"].values * 100))
    converted = {c.mnemonic: c for c in petro.compute(w, p)}
    for name in ("PHIT", "PHIE", "SW"):
        assert np.allclose(converted[name].values, reference[name], equal_nan=True)
    assert "RHOB * 0.001" in converted["PHID"].formula  # the conversion is visible in the formula
    zones = zones_from_tops([Top("A", 7700)], w.stop)
    for c in converted.values():
        w.add_curve(c)
    w.add_curve(Curve("PHIE_PCT", "%", "", converted["PHIE"].values * 100))
    by_fraction = petro.zone_summary(w, zones, "VSH", "PHIE", "SW", 0.4, 0.08, 0.6)[0]
    by_percent = petro.zone_summary(w, zones, "VSH", "PHIE_PCT", "SW", 0.4, 0.08, 0.6)[0]
    assert by_percent.net_reservoir == pytest.approx(by_fraction.net_reservoir)
    assert by_percent.phi_avg == pytest.approx(by_fraction.phi_avg)
