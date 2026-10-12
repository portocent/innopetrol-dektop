"""Project: a working session with several wells (LAS paths, layouts, tops and computed curves).

A project can hold many wells; reading it (`read_project`) gives a WellRef per well without loading
any data, and `load_ref` loads one when it is needed.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from innopetrol.i18n import _
from innopetrol.model.calculator import evaluate
from innopetrol.model.catalog import WellRef, WellSummary, summaries_from_file
from innopetrol.model.core import core_curve
from innopetrol.model.intervals import Interval
from innopetrol.model.io import load_well
from innopetrol.model.layout import LogLayout
from innopetrol.model.location import Location
from innopetrol.model.petro import PetroParams
from innopetrol.model.survey import Survey
from innopetrol.model.tops import Top
from innopetrol.model.well import Curve, Well

FORMAT = "innopetrol-project"
VERSION = 2  # 2: each well has a summary and an "open" flag
SUFFIX = ".ipproj"


class ProjectError(Exception):
    pass


@dataclass
class WellEntry:
    well: Well
    layout: LogLayout
    petro: PetroParams | None = None
    depth_reference: str = "md"
    display_unit: str | None = None
    curve_units: dict[str, str] = field(default_factory=dict)  # curve display units
    open: bool = False  # its window was open (it is opened again with the project)


@dataclass
class LoadResult:
    entries: list[WellEntry] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def well_dict(e: WellEntry) -> dict:
    """Everything the project stores about a loaded well, except where its file is."""
    return {
        "name": e.well.name,
        "layout": e.layout.to_dict(),
        "tops": [t.to_dict() for t in e.well.tops],
        "computed": [
            {"mnemonic": c.mnemonic, "unit": c.unit, "description": c.description, "formula": c.formula}
            for c in e.well.curves.values()
            if c.formula
        ],
        "core": [
            {
                "mnemonic": c.mnemonic,
                "unit": c.unit,
                "description": c.description,
                "depths": c.points[0],
                "values": c.points[1],
            }
            for c in e.well.curves.values()
            if c.points is not None
        ],
        "petro": e.petro.to_dict() if e.petro else None,
        "source": e.well.source,  # frame inside a DLIS file
        "survey": e.well.survey.to_dict() if e.well.survey is not None else None,
        "elevation": e.well.elevation,
        "location": e.well.location.to_dict() if e.well.location is not None else None,
        "intervals": [i.to_dict() for i in e.well.intervals],
        "depth_reference": e.depth_reference,
        "display_unit": e.display_unit,
        "curve_units": e.curve_units,
    }


def save_project(path: str | Path, items: list[WellEntry | WellRef]) -> None:
    """Write a project. Loaded wells come as WellEntry; wells that are not loaded as WellRef, whose
    stored entry is written back unchanged (only the path is made relative to the new location)."""
    path = Path(path)
    wells = []
    for item in items:
        if isinstance(item, WellEntry):
            if item.well.path is None:
                continue
            w, file, summary, is_open = well_dict(item), item.well.path, WellSummary.from_well(item.well), item.open
        else:
            if item.path is None or item.entry is None:
                continue
            w, file, summary, is_open = dict(item.entry), item.path, item.summary, False
        w.update(path=_relative(file, path.parent), summary=summary.to_dict(), open=is_open)
        wells.append(w)
    data = {"format": FORMAT, "version": VERSION, "wells": wells}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_project(path: str | Path) -> list[WellRef]:
    """The wells of a project without loading them (each WellRef keeps its project entry).

    Projects written before version 2 have no summaries; they are read from the file headers. Entries
    without the "open" flag (version 1) count as open, so old projects open as they used to.
    """
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ProjectError(_("could not read the project: {error}").format(error=e)) from e
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ProjectError(_("the file is not an InnoPetrol project"))
    return [_ref(w, path.parent) for w in data.get("wells", [])]


def _ref(w: dict, folder: Path) -> WellRef:
    file = (folder / w["path"]).resolve()
    source = w.get("source")
    ref = WellRef(file, source, WellSummary(w.get("name") or file.stem), entry=w, missing=not file.exists())
    if w.get("summary"):
        ref.summary = WellSummary.from_dict(w["summary"])
    elif not ref.missing:
        try:
            found = dict(summaries_from_file(file))
            ref.summary = found.get(source) or next(iter(found.values()))
        except Exception:  # an unreadable file shows up when the well is loaded
            pass
    return ref


def is_open(ref: WellRef) -> bool:
    """The well's window was open when the project was saved."""
    return bool(ref.entry is not None and ref.entry.get("open", True))


def load_ref(ref: WellRef, errors: list[str]) -> WellEntry | None:
    """Load a well of the project from its file and stored entry. Problems go to `errors`."""
    if ref.path is None or ref.entry is None:
        return None
    entry = _load_entry(ref.entry, ref.path, errors)
    if entry is not None:
        ref.missing = False
        ref.summary = WellSummary.from_well(entry.well)
        entry.open = is_open(ref)
    return entry


def load_project(path: str | Path) -> LoadResult:
    """Read a project and load all its wells."""
    result = LoadResult()
    for ref in read_project(path):
        entry = load_ref(ref, result.errors)
        if entry is not None:
            result.entries.append(entry)
    return result


def _load_entry(w: dict, las_path: Path, errors: list[str]) -> WellEntry | None:
    """One well of a project: its file, then what the project adds to it. Problems go to `errors`."""
    try:
        well = load_well(las_path, w.get("source"))
    except Exception as e:  # any read error is reported and loading continues
        errors.append(f"{w.get('name', las_path.name)}: {e}")
        return None
    well.tops = [Top.from_dict(t) for t in w.get("tops", [])]
    well.intervals = [Interval.from_dict(i) for i in w.get("intervals", [])]
    _restore_position(well, w, errors)  # first: formulas may use TVD
    for c in w.get("core", []):  # before the formulas: they may use core curves
        well.add_curve(
            core_curve(well, c["mnemonic"], c.get("unit", ""), c.get("description", ""), c["depths"], c["values"])
        )
    for c in w.get("computed", []):
        try:
            values = evaluate(c["formula"], well.formula_env())
        except Exception as e:
            errors.append(
                _("{well}: could not recompute {curve}: {error}").format(well=well.name, curve=c["mnemonic"], error=e)
            )
            continue
        well.add_curve(Curve(c["mnemonic"], c.get("unit", ""), c.get("description", ""), values, formula=c["formula"]))
    return WellEntry(
        well,
        LogLayout.from_dict(w.get("layout", {})),
        PetroParams.from_dict(w["petro"]) if w.get("petro") else None,
        w.get("depth_reference", "md"),
        w.get("display_unit"),
        w.get("curve_units", {}),
    )


def _restore_position(well, w: dict, errors: list[str]) -> None:
    """Survey, elevation and surface location saved in the project."""
    if w.get("survey"):
        try:
            well.survey = Survey.from_dict(w["survey"])
        except Exception as e:
            errors.append(_("{well}: invalid survey: {error}").format(well=well.name, error=e))
    if "elevation" in w:
        well.elevation = w["elevation"]
    if w.get("location"):
        try:
            well.location = Location.from_dict(w["location"])
        except (KeyError, TypeError, ValueError):
            errors.append(_("{well}: invalid location").format(well=well.name))


def _relative(target: Path, base: Path) -> str:
    try:
        return os.path.relpath(Path(target).resolve(), base.resolve())
    except ValueError:  # different drive on Windows
        return str(Path(target).resolve())
