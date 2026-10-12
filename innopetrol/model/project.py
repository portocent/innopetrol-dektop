"""Project: a working session with several wells (LAS paths, layouts, tops and computed curves)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from innopetrol.i18n import _
from innopetrol.model.calculator import evaluate
from innopetrol.model.io import load_well
from innopetrol.model.layout import LogLayout
from innopetrol.model.petro import PetroParams
from innopetrol.model.tops import Top
from innopetrol.model.survey import Survey
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
        wells.append({
            "path": _relative(e.well.path, path.parent),
            "name": e.well.name,
            "layout": e.layout.to_dict(),
            "tops": [t.to_dict() for t in e.well.tops],
            "computed": [
                {"mnemonic": c.mnemonic, "unit": c.unit, "description": c.description, "formula": c.formula}
                for c in e.well.curves.values() if c.formula
            ],
            "petro": e.petro.to_dict() if e.petro else None,
            "source": e.well.source,  # frame inside a DLIS file
            "survey": e.well.survey.to_dict() if e.well.survey is not None else None,
            "elevation": e.well.elevation,
            "depth_reference": e.depth_reference,
            "display_unit": e.display_unit,
            "curve_units": e.curve_units,
        })
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
        las_path = (path.parent / w["path"]).resolve()
        try:
            well = load_well(las_path, w.get("source"))
        except Exception as e:  # noqa: BLE001 - any read error is reported and loading continues
            result.errors.append(f"{w.get('name', las_path.name)}: {e}")
            continue
        well.tops = [Top.from_dict(t) for t in w.get("tops", [])]
        # Survey and elevation first: formulas may use TVD.
        if w.get("survey"):
            try:
                well.survey = Survey.from_dict(w["survey"])
            except Exception as e:  # noqa: BLE001
                result.errors.append(_("{well}: invalid survey: {error}").format(well=well.name, error=e))
        if "elevation" in w:
            well.elevation = w["elevation"]
        for c in w.get("computed", []):
            try:
                values = evaluate(c["formula"], well.formula_env())
            except Exception as e:  # noqa: BLE001
                result.errors.append(_("{well}: could not recompute {curve}: {error}").format(
                    well=well.name, curve=c["mnemonic"], error=e))
                continue
            well.add_curve(Curve(c["mnemonic"], c.get("unit", ""), c.get("description", ""), values,
                                 formula=c["formula"]))
        petro = PetroParams.from_dict(w["petro"]) if w.get("petro") else None
        result.entries.append(WellEntry(well, LogLayout.from_dict(w.get("layout", {})), petro,
                                        w.get("depth_reference", "md"), w.get("display_unit"),
                                        w.get("curve_units", {})))
    return result


def _relative(target: Path, base: Path) -> str:
    try:
        return os.path.relpath(Path(target).resolve(), base.resolve())
    except ValueError:  # different drive on Windows
        return str(Path(target).resolve())
