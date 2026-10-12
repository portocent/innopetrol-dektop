"""LAS file loading and the in-memory representation of a well."""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path

import lasio
import numpy as np

from innopetrol.i18n import _, ngettext
from innopetrol.model.intervals import Interval
from innopetrol.model.location import Location, location_from_header
from innopetrol.model.survey import Survey
from innopetrol.model.tops import Top

FEET_UNITS = {"F", "FT", "FEET", "FOOT", "FT.", "FEET."}
# Missing-value markers found in real files even when the header declares a different NULL.
# Only negative markers: 999 or 9999 can be valid depths or readings.
NULL_MARKERS = (-999.0, -999.25, -999.99, -9999.0, -9999.25)
# Missing values lasio should read as NaN: the NULL declared in the header and text markers such as
# "-1.#IND" or "-1.#IO" (how Windows programs print an invalid number). Numeric markers like 9999.25
# are not in the list on purpose (they can be real depths in deep wells); NULL_MARKERS handles them.
LASIO_NULL_POLICY = ["NULL", "(null)", "-", "NA", "INF", "IO", "IND"]
# Values that LAS 1.2 writers put in the WELL value field when the real name is in the description.
_GENERIC_WELL_NAMES = {"", "WELL", "WELL NAME", "WELLNAME", "NAME"}


@dataclass
class Curve:
    mnemonic: str
    unit: str
    description: str
    values: np.ndarray
    formula: str | None = None  # computed curves keep their formula so they can be recomputed
    # Point data (core): the original (depths, values), kept so a project can place them again.
    points: tuple[list[float], list[float]] | None = None

    @property
    def has_data(self) -> bool:
        return bool(np.isfinite(self.values).any())

    @property
    def min(self) -> float:
        return float(np.nanmin(self.values)) if self.has_data else float("nan")

    @property
    def max(self) -> float:
        return float(np.nanmax(self.values)) if self.has_data else float("nan")


@dataclass
class HeaderItem:
    mnemonic: str
    unit: str
    value: str
    description: str


@dataclass
class Well:
    name: str
    path: Path | None
    depth: np.ndarray
    depth_unit: str  # "ft" or "m"
    depth_mnemonic: str = "DEPT"
    header: list[HeaderItem] = field(default_factory=list)
    curves: dict[str, Curve] = field(default_factory=dict)
    tops: list[Top] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # data fixes made while loading, shown to the user
    survey: Survey | None = None
    elevation: float | None = None  # elevation of the depth reference (KB/DF/GL) above sea level
    source: str | None = None  # frame name inside a multi-frame file (DLIS)
    location: Location | None = None  # surface location (from the header or entered by the user)
    intervals: list[Interval] = field(default_factory=list)  # perforations, tests, comments… (MD)

    def __post_init__(self):
        if self.elevation is None:
            self.elevation = elevation_from_header(self.header, self.depth_unit)
        if self.location is None:
            self.location = location_from_header(self.header)

    def tvd(self) -> np.ndarray:
        """True vertical depth of every sample (the well is assumed vertical without a survey)."""
        return self.depth.copy() if self.survey is None else self.survey.tvd_at(self.depth)

    def formula_env(self) -> dict[str, np.ndarray]:
        """Names available in calculator formulas: every curve, plus DEPTH (MD) and TVD of each
        sample in the well's depth unit (a curve with the same name takes precedence)."""
        env = {m: c.values for m, c in self.curves.items()}
        env.setdefault("DEPTH", self.depth)
        if "TVD" not in env:
            env["TVD"] = self.tvd()
        return env

    @classmethod
    def from_las(cls, path: str | Path) -> Well:
        path = Path(path)
        # lasio logs a warning when it switches engines for WRAP=YES files; that is not an error.
        logging.getLogger("lasio").setLevel(logging.ERROR)
        las = lasio.read(
            str(path), encoding=detect_encoding(path), ignore_header_errors=True, null_policy=LASIO_NULL_POLICY
        )
        if not las.curves:
            raise ValueError(_("the file contains no curves"))
        depth = np.asarray(las.index, dtype=float)
        if depth.size < 2:
            raise ValueError(_("the file contains no data"))

        unit_raw = (las.curves[0].unit or "").strip().upper()
        if not unit_raw and "STRT" in las.well:
            unit_raw = (las.well["STRT"].unit or "").strip().upper()
        depth_unit = "ft" if unit_raw in FEET_UNITS else "m"

        header = [HeaderItem(i.mnemonic, i.unit or "", str(i.value), i.descr or "") for i in las.well]
        name = las_well_name(las)
        curves: dict[str, Curve] = {}
        for c in las.curves[1:]:
            mnem = unique_mnemonic(c.mnemonic.strip() or "CURVE", curves)
            curves[mnem] = Curve(mnem, (c.unit or "").strip(), (c.descr or "").strip(), np.asarray(c.data, dtype=float))
        depth, notes = clean_samples(depth, curves)
        if depth.size < 2:
            raise ValueError(_("the file contains no data"))

        return cls(
            notes=notes,
            name=name or path.stem,
            path=path,
            depth=depth,
            depth_unit=depth_unit,
            depth_mnemonic=las.curves[0].mnemonic,
            header=header,
            curves=curves,
        )

    @property
    def start(self) -> float:
        return float(self.depth[0])

    @property
    def stop(self) -> float:
        return float(self.depth[-1])

    @property
    def step(self) -> float:
        return float(np.median(np.diff(self.depth)))

    def header_value(self, mnemonic: str) -> str:
        for h in self.header:
            if h.mnemonic.upper() == mnemonic.upper():
                return h.value
        return ""

    def add_curve(self, curve: Curve, replace: bool = True) -> None:
        if curve.values.shape != self.depth.shape:
            raise ValueError(_("the curve does not have the same number of samples as the depth"))
        if not replace and curve.mnemonic in self.curves:
            raise ValueError(_("a curve named {name} already exists").format(name=curve.mnemonic))
        self.curves[curve.mnemonic] = curve

    def remove_curve(self, mnemonic: str) -> None:
        self.curves.pop(mnemonic, None)

    def value_at(self, mnemonic: str, depth: float) -> float:
        """Interpolated curve value at a depth (NaN outside the range or in gaps)."""
        curve = self.curves.get(mnemonic)
        if curve is None or depth < self.start or depth > self.stop:
            return float("nan")
        i = int(np.searchsorted(self.depth, depth))
        if i == 0:
            return float(curve.values[0])
        d0, d1 = self.depth[i - 1], self.depth[i]
        v0, v1 = curve.values[i - 1], curve.values[i]
        t = 0.0 if d1 == d0 else (depth - d0) / (d1 - d0)
        return float(v0 + (v1 - v0) * t)

    def interval_mask(self, top: float | None, base: float | None) -> np.ndarray:
        mask = np.ones(self.depth.shape, dtype=bool)
        if top is not None:
            mask &= self.depth >= top
        if base is not None:
            mask &= self.depth < base
        return mask

    def to_las(self, path: str | Path, mask: np.ndarray | None = None) -> None:
        las = lasio.LASFile()
        for h in self.header:
            if h.mnemonic.upper() in ("STRT", "STOP", "STEP"):
                continue
            las.well[h.mnemonic] = lasio.HeaderItem(h.mnemonic, h.unit, h.value, h.description)
        sel = slice(None) if mask is None else mask
        unit = "FT" if self.depth_unit == "ft" else "M"
        las.append_curve(self.depth_mnemonic, self.depth[sel], unit=unit, descr="Depth")
        for c in self.curves.values():
            descr = c.description if c.formula is None else f"{c.description} [= {c.formula}]"
            las.append_curve(c.mnemonic, c.values[sel], unit=c.unit, descr=descr)
        las.well["WELL"] = lasio.HeaderItem("WELL", "", self.name, "WELL")
        # Explicit encoding: on Windows Python would default to cp1252 and fail on characters like φ.
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            las.write(f, version=2.0, fmt="%.5f")

    def to_csv(self, path: str | Path, mask: np.ndarray | None = None) -> None:
        sel = slice(None) if mask is None else mask
        names = [self.depth_mnemonic, *self.curves]
        columns = np.column_stack([self.depth[sel]] + [c.values[sel] for c in self.curves.values()])
        # utf-8-sig adds the BOM that Excel on Windows needs to show accented characters correctly.
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(names)
            for row in columns:
                writer.writerow(["" if np.isnan(v) else f"{v:.5f}" for v in row])


# Header items holding the elevation of the log depth reference, in order of preference.
# LMF ("log measured from") says which one applies when present.
_ELEVATION_KEYS = {"KB": ("EKB", "KB", "ELKB", "KBE"), "DF": ("EDF", "DF", "ELDF"), "GL": ("EGL", "GL", "ELGL")}
_ELEVATION_FALLBACK = ("ELZ", "EREF", "EKB", "EDF", "KB", "DF", "ELEV", "EGL", "GL")


def elevation_from_header(header: list[HeaderItem], depth_unit: str) -> float | None:
    by_name = {h.mnemonic.strip().upper(): h for h in header}
    keys: tuple[str, ...] = _ELEVATION_FALLBACK
    lmf = by_name.get("LMF") or by_name.get("DMF")
    if lmf:
        ref = str(lmf.value).strip().upper()
        for code, names in _ELEVATION_KEYS.items():
            if ref.startswith(code) or ref in names:
                keys = names + keys
                break
    for key in keys:
        item = by_name.get(key)
        if item is None:
            continue
        try:
            value = float(str(item.value).replace(",", "."))
        except ValueError:
            continue
        if not np.isfinite(value) or value in NULL_MARKERS:
            continue
        unit = item.unit.strip().upper()
        if unit in FEET_UNITS and depth_unit == "m":
            value *= 0.3048
        elif unit in ("M", "METER", "METERS", "METRES") and depth_unit == "ft":
            value /= 0.3048
        return value
    return None


def detect_encoding(path: str | Path) -> str:
    """Text encoding of a file: UTF-8 (with or without BOM), Windows-1252 or Latin-1.

    Many LAS files from Latin American vendors are Windows-1252 ("Compañía"), others are UTF-8.
    Without this check lasio would read UTF-8 as Windows-1252 and show "CompaÃ±Ã­a".
    """
    raw = Path(path).read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    for enc in ("utf-8", "cp1252"):
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"  # decodes any byte


def clean_samples(depth: np.ndarray, curves: dict[str, Curve]) -> tuple[np.ndarray, list[str]]:
    """Fixes common problems of real LAS files. Returns the clean depth and notes for the user.

    Drawing, interpolation and zone statistics assume strictly increasing depth with no gaps
    in the depth column itself, so rows are filtered, sorted and de-duplicated here.
    """
    notes = []
    markers = 0
    for c in curves.values():
        bad = np.isin(c.values, NULL_MARKERS)
        if bad.any():
            markers += int(bad.sum())
            c.values = np.where(bad, np.nan, c.values)
    if markers:
        notes.append(
            ngettext(
                "{count} value equal to a common null marker (-999, -9999…) was treated as missing",
                "{count} values equal to common null markers (-999, -9999…) were treated as missing",
                markers,
            ).format(count=markers)
        )

    keep = np.isfinite(depth) & ~np.isin(depth, NULL_MARKERS)
    if not keep.all():
        removed = int((~keep).sum())
        notes.append(
            ngettext(
                "{count} row with a null depth was removed", "{count} rows with a null depth were removed", removed
            ).format(count=removed)
        )
    order = np.flatnonzero(keep)
    if depth[order].size > 1 and np.any(np.diff(depth[order]) < 0):
        increasing = depth[order[0]] < depth[order[-1]]
        order = order[np.argsort(depth[order], kind="stable")]
        if increasing:  # only partly out of order: worth telling (bottom-up files are normal)
            notes.append(_("depth was not always increasing; samples were sorted by depth"))
    sorted_depth = depth[order]
    unique = np.concatenate(([True], np.diff(sorted_depth) > 0)) if sorted_depth.size else sorted_depth.astype(bool)
    if not unique.all():
        repeated = int((~unique).sum())
        notes.append(
            ngettext(
                "{count} sample with a repeated depth was removed (the first one is kept)",
                "{count} samples with a repeated depth were removed (the first one is kept)",
                repeated,
            ).format(count=repeated)
        )
    order = order[unique]
    for c in curves.values():
        c.values = c.values[order].copy()
    return depth[order].copy(), notes


def las_well_name(las) -> str:
    if "WELL" not in las.well:
        return ""
    item = las.well["WELL"]
    for candidate in (str(item.value).strip(), str(item.descr or "").strip()):
        if candidate.upper() not in _GENERIC_WELL_NAMES:
            return candidate
    return ""


def unique_mnemonic(name: str, existing: dict) -> str:
    if name not in existing:
        return name
    n = 2
    while f"{name}_{n}" in existing:
        n += 1
    return f"{name}_{n}"
