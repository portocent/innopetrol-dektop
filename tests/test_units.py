import numpy as np
import pytest

from innopetrol.model import units


@pytest.mark.parametrize(
    "raw,key",
    [
        ("G/C3", "g/cm3"),
        ("g/cc", "g/cm3"),
        ("K/M3", "kg/m3"),
        ("US/F", "us/ft"),
        ("usec/ft", "us/ft"),
        ("DEC", "v/v"),
        ("V/V", "v/v"),
        ("PU", "%"),
        ("DEGF", "degF"),
        ("deg C", "degC"),
        ("PSIA", "psi"),
        ("IN", "in"),
        ("F", None),
        ("C", None),
        ("GAPI", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize(raw, key):
    assert units.normalize(raw) == key


@pytest.mark.parametrize(
    "value,a,b,expected",
    [
        (2.65, "G/C3", "kg/m3", 2650),
        (100, "US/F", "us/m", 328.084),
        (25, "PU", "v/v", 0.25),
        (212, "DEGF", "degC", 100),
        (-40, "degC", "degF", -40),
        (1, "bar", "psi", 14.5038),
        (8.5, "IN", "mm", 215.9),
    ],
)
def test_convert(value, a, b, expected):
    assert units.convert(value, a, b) == pytest.approx(expected, rel=1e-5)


def test_round_trip_and_nan():
    v = np.array([1.9, np.nan, 2.7])
    back = units.convert(units.convert(v, "g/cm3", "kg/m3"), "kg/m3", "g/cm3")
    assert np.allclose(back, v, equal_nan=True)


def test_incompatible_or_unknown_units_raise():
    with pytest.raises(ValueError):
        units.convert(1, "g/cm3", "psi")
    with pytest.raises(ValueError):
        units.convert(1, "GAPI", "v/v")


def test_same_unknown_unit_is_identity():
    assert units.convert(5, "GAPI", "GAPI") == 5


def test_linear_coefficients_match_convert():
    for a, b in (("degF", "degC"), ("g/cm3", "kg/m3"), ("%", "v/v")):
        scale, shift = units.linear_coefficients(a, b)
        assert 77 * scale + shift == pytest.approx(units.convert(77, a, b))


def test_system_units():
    assert units.system_unit("G/C3", "metric") == "kg/m3"
    assert units.system_unit("G/C3", "oilfield") is None  # already the preferred unit
    assert units.system_unit("PU", "oilfield") == "v/v"
    assert units.system_unit("GAPI", "metric") is None and units.system_unit("G/C3", "file") is None
    assert units.convertible("US/F") == ["us/ft", "us/m"] and units.convertible("GAPI") == []
