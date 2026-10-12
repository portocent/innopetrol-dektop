"""Reference cases with known answers, worked out by hand from the published equations.

Unlike the other petrophysics tests (which compare the formulas with InnoPetrol's own NumPy
functions), these check the numbers against values anyone can verify with a calculator.
"""

import math

import numpy as np
import pytest

from innopetrol.model import petro
from innopetrol.model.calculator import evaluate
from innopetrol.model.survey import Survey
from innopetrol.model.well import Curve, Well


def one_sample_well(**curves) -> Well:
    depth = np.array([1000.0, 1000.5])
    return Well("ref", None, depth, "m", curves={m: Curve(m, u, "", np.full(2, v)) for m, (u, v) in curves.items()})


def computed(well, **params) -> dict[str, float]:
    p = petro.PetroParams(**params)
    env = well.formula_env()
    out = {}
    for spec in petro.build_formulas(well, p):
        env[spec.mnemonic] = evaluate(spec.formula, env)
        out[spec.mnemonic] = float(env[spec.mnemonic][0])
    return out


def test_archie_classic_example():
    # Sw = (a·Rw / (φ^m·Rt))^(1/n) = (0.05 / (0.04·20))^(1/2) = 0.0625^0.5 = 0.25
    w = one_sample_well(RHOB=("G/C3", 2.65 - 0.2 * 1.65), RT=("OHMM", 20.0))
    r = computed(w, rhob_curve="RHOB", rt_curve="RT", rw=0.05)
    assert r["PHIE"] == pytest.approx(0.20)
    assert r["SW"] == pytest.approx(0.25)


def test_archie_humble_constants():
    # a = 0.62, m = 2.15: Sw = (0.62·0.05 / (0.2^2.15·20))^(1/2), computed here by hand.
    expected = math.sqrt(0.62 * 0.05 / (0.2**2.15 * 20))
    w = one_sample_well(RHOB=("G/C3", 2.65 - 0.2 * 1.65), RT=("OHMM", 20.0))
    assert computed(w, rhob_curve="RHOB", rt_curve="RT", rw=0.05, a=0.62, m=2.15)["SW"] == pytest.approx(expected)
    assert expected == pytest.approx(0.2221, abs=1e-4)  # 0.2^2.15 = 0.03144 → 0.031/0.6288 = 0.0493 → √ = 0.2221


@pytest.mark.parametrize(
    "method, igr, vsh",
    [
        ("linear", 0.5, 0.5),
        ("larionov_tertiary", 0.5, 0.083 * (2**1.85 - 1)),  # 0.1997
        ("larionov_older", 0.5, 0.33),  # 0.33·(2¹ − 1)
        ("larionov_tertiary", 0.0, 0.0),
        ("larionov_older", 1.0, 0.99),  # 0.33·(2² − 1)
    ],
)
def test_vsh_methods(method, igr, vsh):
    gr = 20 + igr * 100  # clean 20, shale 120
    w = one_sample_well(GR=("GAPI", gr))
    assert computed(w, gr_curve="GR", gr_clean=20, gr_shale=120, vsh_method=method)["VSH"] == pytest.approx(
        vsh, abs=1e-4
    )


@pytest.mark.parametrize("rho_ma", [2.65, 2.71, 2.87])  # sandstone, limestone, dolomite
def test_density_porosity_end_points(rho_ma):
    at_matrix = one_sample_well(RHOB=("G/C3", rho_ma))
    assert computed(at_matrix, rhob_curve="RHOB", rho_ma=rho_ma)["PHIT"] == pytest.approx(0.0)
    # 25 % porosity filled with fresh water: ρb = 0.75·ρma + 0.25·1.0
    w = one_sample_well(RHOB=("G/C3", 0.75 * rho_ma + 0.25))
    assert computed(w, rhob_curve="RHOB", rho_ma=rho_ma)["PHIT"] == pytest.approx(0.25)


def test_density_in_kg_m3_gives_the_same_porosity():
    w = one_sample_well(RHOB=("KG/M3", 2320.0))  # 2.32 g/cm³ → φ = 0.33/1.65 = 0.2
    assert computed(w, rhob_curve="RHOB")["PHIT"] == pytest.approx(0.2)


def test_shaly_sand_models_without_shale_equal_archie():
    w = one_sample_well(GR=("GAPI", 20.0), RHOB=("G/C3", 2.32), RT=("OHMM", 20.0))
    base = {"gr_curve": "GR", "gr_clean": 20, "gr_shale": 120, "rhob_curve": "RHOB", "rt_curve": "RT", "rw": 0.05}
    for model in ("simandoux", "indonesia"):
        assert computed(w, sw_model=model, **base)["SW"] == pytest.approx(0.25), model


def test_water_line_gives_sw_one():
    # Rt = Ro = a·Rw/φ^m = 0.05/0.04 = 1.25 ohm·m → Sw = 1
    w = one_sample_well(RHOB=("G/C3", 2.32), RT=("OHMM", 1.25))
    assert computed(w, rhob_curve="RHOB", rt_curve="RT", rw=0.05)["SW"] == pytest.approx(1.0)


def test_arps_by_hand():
    # Rw2 = 0.1·(75 + 6.77)/(200 + 6.77) = 0.0395 ohm·m
    assert petro.rw_at_temperature(0.1, 75, 200, "degF") == pytest.approx(0.1 * 81.77 / 206.77)
    assert petro.rw_at_temperature(0.1, 75, 200, "degF") == pytest.approx(0.0395, abs=1e-4)
    # The same water in °C: 23.9 °C → 93.3 °C
    assert petro.rw_at_temperature(0.1, 23.89, 93.33, "degC") == pytest.approx(0.0395, abs=2e-4)


def test_minimum_curvature_quarter_circle():
    # Building from vertical to horizontal along a quarter circle of radius R: TVD = R, displacement = R.
    radius = 1000.0
    s = Survey(np.array([0.0, math.pi * radius / 2]), np.array([0.0, 90.0]), np.array([0.0, 0.0]))
    assert (
        s.tvd[-1] == pytest.approx(radius) and s.north[-1] == pytest.approx(radius) and s.east[-1] == pytest.approx(0)
    )
    # Halfway along the arc (45°): TVD = R·sin 45°, displacement = R·(1 − cos 45°).
    tvd, north, _east = s.position([math.pi * radius / 4])
    assert tvd[0] == pytest.approx(radius * math.sin(math.pi / 4))
    assert north[0] == pytest.approx(radius * (1 - math.cos(math.pi / 4)))


def test_vertical_well_tvd_equals_md():
    s = Survey(np.array([0.0, 1000, 3000]), np.zeros(3), np.zeros(3))
    assert s.tvd_at([2500.0])[0] == pytest.approx(2500.0)
