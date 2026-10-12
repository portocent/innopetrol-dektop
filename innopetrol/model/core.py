"""Core (laboratory) data: point measurements imported from CSV and placed on the log's depth grid.

A core curve is NaN everywhere except at the samples nearest to each core depth, so it is drawn as
points over the log curves. The original depths and values are kept (Curve.points) so a project can
save them and place them again when it is reopened.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from innopetrol.model.text_tables import find_column, is_number, parse_number, read_rows
from innopetrol.model.well import Curve

_DEPTH_COLS = ("depth", "md", "prof", "profundidad", "core depth", "sample depth", "dept")
_UNIT = re.compile(r"[\(\[]\s*([^\)\]]*)\s*[\)\]]")


@dataclass
class CoreTable:
    depths: np.ndarray
    columns: dict[str, tuple[str, np.ndarray]]  # header name -> (unit, values)


def load_core_csv(path: str | Path) -> CoreTable:
    """Reads a core table: a depth column and numeric columns, units in parentheses or brackets
    ("Porosity (%)"). Raises ValueError if there is no depth column or no numeric data."""
    rows = read_rows(path)
    if len(rows) < 2 or is_number(rows[0][0]):
        raise ValueError("header")
    head = rows[0]
    depth_i = find_column(head, _DEPTH_COLS)
    if depth_i is None:
        raise ValueError(", ".join(head))
    data = []
    for r in rows[1:]:
        try:
            depth = parse_number(r[depth_i])
        except (ValueError, IndexError):
            continue
        values = []
        for i in range(len(head)):
            try:
                values.append(parse_number(r[i]) if i < len(r) else np.nan)
            except ValueError:
                values.append(np.nan)
        values[depth_i] = depth
        data.append(values)
    if not data:
        raise ValueError("data")
    table = np.asarray(data, float)
    columns = {}
    for i, name in enumerate(head):
        if i == depth_i or not np.isfinite(table[:, i]).any():
            continue
        unit = _UNIT.search(name)
        columns[name] = (unit.group(1).strip() if unit else "", table[:, i])
    return CoreTable(table[:, depth_i], columns)


def core_mnemonic(name: str) -> str:
    """CORE_POROSITY from "Porosity (%)": letters, digits and _ only."""
    base = _UNIT.sub("", name).strip().upper()
    base = re.sub(r"[^A-Z0-9]+", "_", base).strip("_") or "VALUE"
    return f"CORE_{base}"


def place_on_grid(depth: np.ndarray, core_depths: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Values on the log's depth grid: each core sample at the nearest log sample (averaged if several
    fall on the same one); samples farther than one log step from any core depth stay NaN."""
    out = np.full(depth.shape, np.nan)
    ok = np.isfinite(core_depths) & np.isfinite(values)
    if not ok.any() or depth.size < 2:
        return out
    step = np.median(np.abs(np.diff(depth)))
    idx = np.clip(np.searchsorted(depth, core_depths[ok]), 1, depth.size - 1)
    nearest = np.where(np.abs(depth[idx - 1] - core_depths[ok]) <= np.abs(depth[idx] - core_depths[ok]), idx - 1, idx)
    close = np.abs(depth[nearest] - core_depths[ok]) <= step
    sums = np.bincount(nearest[close], weights=values[ok][close], minlength=depth.size)
    counts = np.bincount(nearest[close], minlength=depth.size)
    with np.errstate(invalid="ignore"):
        out[counts > 0] = sums[counts > 0] / counts[counts > 0]
    return out


def core_curve(well, mnemonic: str, unit: str, description: str, depths, values) -> Curve:
    depths, values = np.asarray(depths, float), np.asarray(values, float)
    curve = Curve(mnemonic, unit, description, place_on_grid(well.depth, depths, values))
    curve.points = (depths.tolist(), values.tolist())
    return curve
