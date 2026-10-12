"""Curve units: recognition of the spellings found in LAS/DLIS files and conversion.

Stored data always stays in the file's units. Conversions are applied when displaying a curve
(per-curve choice or a unit system preset) and, explicitly, inside calculations that need a
specific unit (e.g. density in g/cm³ for density porosity).

Units the program does not recognize are never converted: a wrong guess is worse than no
conversion.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from innopetrol.i18n import N_


@dataclass(frozen=True)
class Unit:
    key: str  # canonical name used internally and in projects
    label: str  # shown to the user
    dimension: str
    factor: float  # value * factor + offset = value in the dimension's base unit
    offset: float = 0.0


_UNITS = [
    Unit("m", "m", "length", 1.0), Unit("ft", "ft", "length", 0.3048), Unit("in", "in", "length", 0.0254),
    Unit("mm", "mm", "length", 0.001), Unit("cm", "cm", "length", 0.01),
    Unit("g/cm3", "g/cm³", "density", 1000.0), Unit("kg/m3", "kg/m³", "density", 1.0),
    Unit("us/ft", "µs/ft", "slowness", 1 / 0.3048), Unit("us/m", "µs/m", "slowness", 1.0),
    Unit("v/v", "v/v", "fraction", 1.0), Unit("%", "%", "fraction", 0.01),
    Unit("degC", "°C", "temperature", 1.0), Unit("degF", "°F", "temperature", 5 / 9, -32 * 5 / 9),
    Unit("psi", "psi", "pressure", 6894.757293), Unit("kPa", "kPa", "pressure", 1000.0),
    Unit("MPa", "MPa", "pressure", 1e6), Unit("bar", "bar", "pressure", 1e5),
]
UNITS = {u.key: u for u in _UNITS}

# Spellings seen in real files (compared upper-case, without spaces). Ambiguous bare letters such
# as "F" (feet or Fahrenheit) or "C" are deliberately absent.
_ALIASES = {
    "m": ("M", "METER", "METERS", "METRE", "METRES"),
    "ft": ("FT", "FEET", "FOOT"),
    "in": ("IN", "INCH", "INCHES", "\""),
    "mm": ("MM",), "cm": ("CM",),
    "g/cm3": ("G/C3", "G/CC", "GM/CC", "G/CM3", "GR/CC", "GRAM/CC", "GC3", "GM/C3", "G/CM³", "GR/CM3"),
    "kg/m3": ("K/M3", "KG/M3", "KGM3", "KG/M³"),
    "us/ft": ("US/F", "US/FT", "USEC/FT", "USEC/F", "US/FOOT", "µS/FT", "µS/F", "USF"),
    "us/m": ("US/M", "USEC/M", "µS/M", "USM"),
    "v/v": ("V/V", "DEC", "FRAC", "FRACTION", "M3/M3", "CFCF", "DECIMAL", "CU.FT/CU.FT"),
    "%": ("%", "PU", "P.U.", "PERCENT", "PCT", "PERC"),
    "degC": ("DEGC", "DEG C", "°C", "DEGCEL", "CELSIUS"),
    "degF": ("DEGF", "DEG F", "°F", "DEGFAH", "FAHRENHEIT"),
    "psi": ("PSI", "PSIA", "PSIG", "LBF/IN2"),
    "kPa": ("KPA",), "MPa": ("MPA",), "bar": ("BAR", "BARS"),
}
_ALIAS_INDEX = {alias.replace(" ", ""): key for key, aliases in _ALIASES.items() for alias in aliases}

SYSTEMS = {
    # Display names (translated with _() when shown) and the preferred unit per dimension.
    "file": (N_("As in the file"), {}),
    "oilfield": (N_("Oilfield (ft, g/cm³, µs/ft, °F, psi, in)"),
                 {"length": "in", "density": "g/cm3", "slowness": "us/ft", "temperature": "degF", "pressure": "psi",
                  "fraction": "v/v"}),
    "metric": (N_("Metric (m, kg/m³, µs/m, °C, kPa, mm)"),
               {"length": "mm", "density": "kg/m3", "slowness": "us/m", "temperature": "degC", "pressure": "kPa",
                "fraction": "v/v"}),
}
SYSTEM_DEPTH_UNIT = {"file": None, "oilfield": "ft", "metric": "m"}


def normalize(unit: str | None) -> str | None:
    """Canonical key of a unit string from a file, or None if it is not recognized."""
    if not unit:
        return None
    text = unit.strip()
    if text in UNITS:
        return text
    return _ALIAS_INDEX.get(text.upper().replace(" ", ""))


def label(unit: str | None) -> str:
    """Display text for a unit (canonical keys get their nice label, anything else is shown as is)."""
    if unit in UNITS:
        return UNITS[unit].label
    return unit or ""


def convertible(unit: str | None) -> list[str]:
    """Canonical units a curve in `unit` can be shown in (empty if the unit is unknown)."""
    key = normalize(unit)
    if key is None:
        return []
    dim = UNITS[key].dimension
    return [u.key for u in _UNITS if u.dimension == dim]


def convert(values, from_unit: str | None, to_unit: str | None) -> np.ndarray:
    """Converts values between units of the same dimension. Raises ValueError otherwise."""
    values = np.asarray(values, dtype=float)
    a, b = normalize(from_unit), normalize(to_unit)
    if a == b and a is not None or (from_unit or "") == (to_unit or ""):
        return values
    if a is None or b is None or UNITS[a].dimension != UNITS[b].dimension:
        raise ValueError(f"cannot convert {from_unit!r} to {to_unit!r}")
    ua, ub = UNITS[a], UNITS[b]
    return ((values * ua.factor + ua.offset) - ub.offset) / ub.factor


def linear_coefficients(from_unit: str | None, to_unit: str | None) -> tuple[float, float]:
    """(scale, shift) so that converted = value * scale + shift. Used to write conversions into formulas."""
    a, b = normalize(from_unit), normalize(to_unit)
    if a is None or b is None or a == b:
        return 1.0, 0.0
    ua, ub = UNITS[a], UNITS[b]
    return ua.factor / ub.factor, (ua.offset - ub.offset) / ub.factor


def system_unit(file_unit: str | None, system: str) -> str | None:
    """Unit a curve should be displayed in under a unit system (None = keep the file unit)."""
    key = normalize(file_unit)
    if key is None or system not in SYSTEMS:
        return None
    target = SYSTEMS[system][1].get(UNITS[key].dimension)
    return target if target and target != key else None
