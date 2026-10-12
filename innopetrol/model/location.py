"""Surface location of a well and its trajectory on a map.

Coordinates come from the file header (X/Y or latitude/longitude, in many spellings and in
decimal or degrees-minutes-seconds) or are entered by the user. The survey's north/east offsets
place the trajectory on the map.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass

import numpy as np

FEET = 0.3048
M_PER_DEG_LAT = 111_320.0  # meters per degree of latitude (spherical approximation, enough for a map)

# Header mnemonic pairs, in order of preference.
_PROJECTED = (
    ("XCOORD", "YCOORD"),
    ("X", "Y"),
    ("XWELL", "YWELL"),
    ("EAST", "NORT"),
    ("EAST", "NORTH"),
    ("EASTING", "NORTHING"),
    ("UTMX", "UTMY"),
    ("XLOC", "YLOC"),
    ("SURFX", "SURFY"),
    ("X_COORD", "Y_COORD"),
)
_GEOGRAPHIC = (("LATI", "LONG"), ("LAT", "LON"), ("LATITUDE", "LONGITUDE"), ("SLAT", "SLON"), ("LAT", "LONG"))
_FEET_UNITS = {"F", "FT", "FEET", "FOOT", "USFT", "FTUS"}


@dataclass
class Location:
    x: float  # easting, or longitude in degrees
    y: float  # northing, or latitude in degrees
    geographic: bool = False
    unit: str = "m"  # map unit of projected coordinates: "m" or "ft" (ignored if geographic)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Location:
        return cls(float(d["x"]), float(d["y"]), bool(d.get("geographic", False)), str(d.get("unit", "m")))


_DMS = re.compile(r"([-+]?\d+(?:[.,]\d+)?)")


def parse_coordinate(text: str) -> float | None:
    """Decimal ("-58.44", "58,44 S") or degrees-minutes-seconds ("58° 26' 29.9\\" S", "N 58 26 29.9").

    S and W hemispheres give negative values. None if no number is found.
    """
    if text is None:
        return None
    s = str(text).strip().upper()
    if not s:
        return None
    numbers = [float(n.replace(",", ".")) for n in _DMS.findall(s)]
    if not numbers or len(numbers) > 3:
        return None
    sign = -1.0 if numbers[0] < 0 else 1.0
    value = abs(numbers[0])
    for i, part in enumerate(numbers[1:], start=1):
        value += part / 60**i
    if re.search(r"(^|[^A-Z])[SW]([^A-Z]|$)", s) or re.search(r"\d[SW]", s):
        sign = -1.0
    value *= sign
    return value if math.isfinite(value) else None


def location_from_header(header) -> Location | None:
    by_name = {h.mnemonic.strip().upper(): h for h in header}
    for lat_key, lon_key in _GEOGRAPHIC:
        lat, lon = by_name.get(lat_key), by_name.get(lon_key)
        if lat and lon:
            y, x = parse_coordinate(lat.value), parse_coordinate(lon.value)
            if x is not None and y is not None and abs(y) <= 90 and abs(x) <= 180 and (x, y) != (0, 0):
                return Location(x, y, geographic=True)
    for x_key, y_key in _PROJECTED:
        xi, yi = by_name.get(x_key), by_name.get(y_key)
        if xi and yi:
            x, y = _number(xi.value), _number(yi.value)
            if x is not None and y is not None and (x, y) != (0, 0) and min(x, y) > -1e8:
                unit = "ft" if xi.unit.strip().upper() in _FEET_UNITS else "m"
                return Location(x, y, geographic=False, unit=unit)
    return None


def _number(text) -> float | None:
    try:
        v = float(str(text).strip().replace(",", "."))
    except ValueError:
        return None
    return v if math.isfinite(v) and v not in (-999.25, -999.0, -9999.0) else None


def trajectory(location: Location, survey, depth_unit: str) -> tuple[np.ndarray, np.ndarray]:
    """Map coordinates (x, y) of the survey stations, starting at the surface location."""
    if survey is None:
        return np.array([location.x]), np.array([location.y])
    to_m = FEET if depth_unit == "ft" else 1.0
    north_m, east_m = survey.north * to_m, survey.east * to_m
    if location.geographic:
        lat = location.y + north_m / M_PER_DEG_LAT
        lon = location.x + east_m / (M_PER_DEG_LAT * max(math.cos(math.radians(location.y)), 1e-6))
        return lon, lat
    per_unit = FEET if location.unit == "ft" else 1.0
    return location.x + east_m / per_unit, location.y + north_m / per_unit
