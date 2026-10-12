"""The wells of a project, loaded or not.

A project can hold hundreds of wells. Each one is a WellRef: where its file is, a short summary
(name, depth range, curves, location…) and, while it is not loaded, the project entry it came from.
The summary is enough to list, filter and map the wells without reading their data; the data is
read only when a well is opened or used by a tool.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

from innopetrol.model.io import load_wells
from innopetrol.model.location import Location, location_from_header
from innopetrol.model.mnemonics import FAMILIES, family_of
from innopetrol.model.well import FEET_UNITS, HeaderItem, Well, detect_encoding, las_well_name, unique_mnemonic


@dataclass
class WellSummary:
    name: str
    depth_unit: str = "m"
    start: float = float("nan")
    stop: float = float("nan")
    curves: list[tuple[str, str]] = field(default_factory=list)  # (mnemonic, unit)
    location: Location | None = None
    tops: int = 0
    uwi: str = ""
    field_name: str = ""
    company: str = ""

    @classmethod
    def from_well(cls, well: Well) -> WellSummary:
        return cls(
            name=well.name,
            depth_unit=well.depth_unit,
            start=float(well.start),
            stop=float(well.stop),
            curves=[(m, c.unit) for m, c in well.curves.items()],
            location=well.location,
            tops=len(well.tops),
            uwi=well.header_value("UWI") or well.header_value("API"),
            field_name=well.header_value("FLD"),
            company=well.header_value("COMP"),
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["curves"] = [list(c) for c in self.curves]
        d["location"] = self.location.to_dict() if self.location else None
        return d

    @classmethod
    def from_dict(cls, d: dict) -> WellSummary:
        location = Location.from_dict(d["location"]) if d.get("location") else None
        return cls(
            name=str(d.get("name", "")),
            depth_unit=str(d.get("depth_unit", "m")),
            start=float(d.get("start", float("nan"))),
            stop=float(d.get("stop", float("nan"))),
            curves=[(str(m), str(u)) for m, u in d.get("curves", [])],
            location=location,
            tops=int(d.get("tops", 0)),
            uwi=str(d.get("uwi", "")),
            field_name=str(d.get("field_name", "")),
            company=str(d.get("company", "")),
        )

    def text(self) -> str:
        """Text that a search looks in: name, UWI, field and company."""
        return " ".join((self.name, self.uwi, self.field_name, self.company)).lower()


@dataclass(eq=False)  # compared by identity: two references to the same file are still two wells
class WellRef:
    path: Path | None
    source: str | None
    summary: WellSummary
    entry: dict | None = None  # the project entry while the well is not loaded (written back unchanged)
    missing: bool = False  # the file was not found

    @property
    def name(self) -> str:
        return self.summary.name

    @classmethod
    def from_well(cls, well: Well) -> WellRef:
        return cls(well.path, well.source, WellSummary.from_well(well))

    def same_file(self, other: WellRef) -> bool:
        """Both point to the same well of the same file."""
        return (
            self.path is not None
            and other.path is not None
            and self.source == other.source
            and (self.path.resolve() == other.path.resolve())
        )


def summaries_from_file(path: str | Path) -> list[tuple[str | None, WellSummary]]:
    """(source, summary) of every well in a file, reading as little as possible.

    LAS: only the header (the data section is skipped). DLIS: the file is read (dlisio is fast and the
    curves are needed to know the frames).
    """
    path = Path(path)
    if path.suffix.lower() != ".las":
        return [(w.source, WellSummary.from_well(w)) for w in load_wells(path)]
    import lasio

    logging.getLogger("lasio").setLevel(logging.ERROR)
    las = lasio.read(str(path), encoding=detect_encoding(path), ignore_header_errors=True, ignore_data=True)
    header = [HeaderItem(i.mnemonic, i.unit or "", str(i.value), i.descr or "") for i in las.well]

    def value(mnemonic: str) -> str:
        item = next((h for h in header if h.mnemonic.upper() == mnemonic), None)
        return item.value.strip() if item else ""

    def number(mnemonic: str) -> float:
        try:
            return float(value(mnemonic).replace(",", "."))
        except ValueError:
            return float("nan")

    unit_raw = (las.curves[0].unit or "").strip().upper() if las.curves else ""
    if not unit_raw and "STRT" in las.well:
        unit_raw = (las.well["STRT"].unit or "").strip().upper()
    start, stop = sorted((number("STRT"), number("STOP")))
    curves: dict[str, str] = {}  # the same mnemonics a full load gives (duplicates numbered)
    for c in las.curves[1:]:
        curves[unique_mnemonic(c.mnemonic.strip() or "CURVE", curves)] = (c.unit or "").strip()
    summary = WellSummary(
        name=las_well_name(las) or path.stem,
        depth_unit="ft" if unit_raw in FEET_UNITS else "m",
        start=start,
        stop=stop,
        curves=list(curves.items()),
        location=location_from_header(header),
        uwi=value("UWI") or value("API"),
        field_name=value("FLD"),
        company=value("COMP"),
    )
    return [(None, summary)]


def matching_curves(summary: WellSummary, curve: str) -> list[str]:
    """Curves of the well that match `curve`: a family key (gamma_ray, density…) or a mnemonic
    (case-insensitive)."""
    if curve in FAMILIES:
        return [m for m, _unit in summary.curves if family_of(m) == curve]
    wanted = curve.strip().upper()
    return [m for m, _unit in summary.curves if m.upper() == wanted]


def matches(summary: WellSummary, text: str = "", curve: str = "") -> bool:
    """The well passes a filter: every word of `text` is in its name, UWI, field or company, and it
    has the `curve` (see matching_curves). Empty parts of the filter match every well."""
    haystack = summary.text()
    if any(word not in haystack for word in text.lower().split()):
        return False
    return not curve or bool(matching_curves(summary, curve))
