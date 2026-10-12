"""Minimum curvature checked against geometries with an exact answer."""

import math

import numpy as np
import pytest

from innopetrol.model.survey import Survey, SurveyError, load_survey_csv


def test_vertical_well():
    s = Survey(np.array([0, 1000, 2000]), np.zeros(3), np.zeros(3))
    assert np.allclose(s.tvd, [0, 1000, 2000])
    assert np.allclose(s.tvd_at([500, 1500, 2500]), [500, 1500, 2500])  # also beyond the last station


def test_constant_inclination_slant():
    s = Survey(np.array([0, 1000]), np.array([30, 30]), np.array([45, 45]))
    tvd, north, east = s.position([1000])
    assert tvd[0] == pytest.approx(1000 * math.cos(math.radians(30)))
    horizontal = 1000 * math.sin(math.radians(30))
    assert north[0] == pytest.approx(horizontal * math.cos(math.radians(45)))
    assert east[0] == pytest.approx(horizontal * math.sin(math.radians(45)))


def test_circular_build_is_exact_between_stations():
    """A 0°→90° build with radius R: TVD = R·sin(θ), departure = R·(1 − cos θ) at every point."""
    radius = 1000.0
    arc = radius * math.pi / 2
    s = Survey(np.array([0.0, arc]), np.array([0.0, 90.0]), np.array([0.0, 0.0]))  # only 2 stations
    md = np.linspace(0, arc, 25)
    theta = md / radius
    tvd, north, _east = s.position(md)
    assert np.allclose(tvd, radius * np.sin(theta), atol=1e-6)
    assert np.allclose(north, radius * (1 - np.cos(theta)), atol=1e-6)


def test_tie_in_added_when_first_station_is_deep():
    s = Survey(np.array([500, 1000]), np.array([0, 10]), np.array([0, 0]))
    assert s.md[0] == 0 and s.tvd[1] == pytest.approx(500)


def test_horizontal_section_tvd_stays_flat():
    s = Survey(np.array([0, 1000, 1200, 2200]), np.array([0, 0, 90, 90]), np.array([0, 0, 0, 0]))
    tvd = s.tvd_at([2000, 2200])
    assert tvd[0] == pytest.approx(tvd[1])


def test_invalid_inclination():
    with pytest.raises(SurveyError):
        Survey(np.array([0, 100]), np.array([0, 200]), np.array([0, 0]))


def test_load_csv_spanish_header_and_comma_decimals(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text(
        "Profundidad;Inclinación;Azimut\n(m);(deg);(deg)\n0;0;0\n500,5;10,25;45\n1000;20;90\n", encoding="utf-8"
    )
    s = load_survey_csv(p)
    assert s.md.tolist() == [0, 500.5, 1000] and s.inc[1] == 10.25


def test_load_headerless_whitespace(tmp_path):
    p = tmp_path / "s.txt"
    p.write_text("# survey\n0 0 0\n1000 0 0\n2000 30 120\n")
    assert load_survey_csv(p).md.size == 3


def test_load_without_required_columns(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("A,B,C\n1,2,3\n")
    with pytest.raises(SurveyError):
        load_survey_csv(p)
