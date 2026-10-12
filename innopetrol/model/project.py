"""Proyecto: sesión de trabajo con varios pozos (rutas LAS, layouts, topes y curvas calculadas)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from innopetrol.model.calculator import evaluate
from innopetrol.model.layout import LogLayout
from innopetrol.model.petro import PetroParams
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
        })
    data = {"format": FORMAT, "version": VERSION, "wells": wells}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_project(path: str | Path) -> LoadResult:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ProjectError(f"no se pudo leer el proyecto: {e}") from e
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ProjectError("el archivo no es un proyecto de InnoPetrol")

    result = LoadResult()
    for w in data.get("wells", []):
        las_path = (path.parent / w["path"]).resolve()
        try:
            well = Well.from_las(las_path)
        except Exception as e:  # noqa: BLE001 - cualquier error de lectura se informa y se sigue
            result.errors.append(f"{w.get('name', las_path.name)}: {e}")
            continue
        well.tops = [Top.from_dict(t) for t in w.get("tops", [])]
        for c in w.get("computed", []):
            try:
                values = evaluate(c["formula"], {m: cv.values for m, cv in well.curves.items()})
            except Exception as e:  # noqa: BLE001
                result.errors.append(f"{well.name}: no se pudo recalcular {c['mnemonic']}: {e}")
                continue
            well.add_curve(Curve(c["mnemonic"], c.get("unit", ""), c.get("description", ""), values,
                                 formula=c["formula"]))
        petro = PetroParams.from_dict(w["petro"]) if w.get("petro") else None
        result.entries.append(WellEntry(well, LogLayout.from_dict(w.get("layout", {})), petro))
    return result


def _relative(target: Path, base: Path) -> str:
    try:
        return os.path.relpath(Path(target).resolve(), base.resolve())
    except ValueError:  # distinto disco en Windows
        return str(Path(target).resolve())
