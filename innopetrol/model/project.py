"""Project: a working session with several wells (LAS paths, layouts, tops and computed curves)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from innopetrol.i18n import _
from innopetrol.model.calculator import evaluate
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
VERSION = 1
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


@dataclass
class LoadResult:
    entries: list[WellEntry] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def save_project(path: str | Path, entries: list[WellEntry]) -> None:
    path = Path(path)
    wells = []
    for e in entries:
        if e.well.path is None:
            continue
        wells.append(
            {
                "path": _relative(e.well.path, path.parent),
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
        )
    data = {"format": FORMAT, "version": VERSION, "wells": wells}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_project(path: str | Path) -> LoadResult:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ProjectError(_("could not read the project: {error}").format(error=e)) from e
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ProjectError(_("the file is not an InnoPetrol project"))

    result = LoadResult()
    for w in data.get("wells", []):
        entry = _load_entry(w, path.parent, result.errors)
        if entry is not None:
            result.entries.append(entry)
    return result


def _load_entry(w: dict, folder: Path, errors: list[str]) -> WellEntry | None:
    """One well of a project: its file, then what the project adds to it. Problems go to `errors`."""
    las_path = (folder / w["path"]).resolve()
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
