"""Formation tops (markers) and the zones between them."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from innopetrol.model.text_tables import find_column, is_number, parse_number, read_rows

PALETTE = ["#c0392b", "#2471a3", "#1e8449", "#b9770e", "#7d3c98", "#117a65", "#a04000", "#2e4053"]


@dataclass
class Top:
    name: str
    depth: float
    color: str = "#c0392b"

    def to_dict(self) -> dict:
        return {"name": self.name, "depth": self.depth, "color": self.color}

    @classmethod
    def from_dict(cls, d: dict) -> Top:
        return cls(str(d["name"]), float(d["depth"]), str(d.get("color", "#c0392b")))


@dataclass
class Zone:
    name: str
    top: float
    base: float


# Column headers accepted in English and Spanish (tops files come from both kinds of projects).
_NAME_COLS = ("name", "nombre", "top", "tope", "marker", "formation", "formacion", "formación", "surface")
_DEPTH_COLS = ("depth", "md", "profundidad", "prof", "tvd")
_WELL_COLS = ("well", "pozo", "uwi", "well_name")


def load_tops_csv(path: str | Path, well_name: str | None = None) -> list[Top]:
    """Reads tops from CSV/TXT. Accepts English or Spanish headers and , ; or tab separators.

    If the file has a well column and `well_name` is given, only that well's rows are kept.
    Without a header the columns are assumed to be: name, depth[, color].
    """
    rows = read_rows(path)
    if not rows:
        return []

    has_header = not is_number(rows[0][1] if len(rows[0]) > 1 else "")
    if has_header:
        head = rows[0]
        name_i = _column(head, _NAME_COLS, 0)
        depth_i = _column(head, _DEPTH_COLS, 1)
        color_i = find_column(head, ("color", "colour"))
        well_i = find_column(head, _WELL_COLS)
        if name_i == depth_i:
            name_i, depth_i = 0, 1
        rows = rows[1:]
    else:
        name_i, depth_i, color_i, well_i = 0, 1, 2, None

    wanted_well = well_name.strip().upper() if well_name else None
    tops: list[Top] = []
    for r in rows:
        if wanted_well and well_i is not None and well_i < len(r) and r[well_i].upper() != wanted_well:
            continue
        try:
            depth = parse_number(r[depth_i])
        except (ValueError, IndexError):
            continue
        color = r[color_i] if color_i is not None and color_i < len(r) and r[color_i] else None
        tops.append(Top(r[name_i], depth, color or PALETTE[len(tops) % len(PALETTE)]))
    return sorted(tops, key=lambda t: t.depth)


def save_tops_csv(path: str | Path, tops: list[Top]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # BOM: Excel on Windows
        w = csv.writer(f)
        w.writerow(["name", "depth", "color"])
        for t in sorted(tops, key=lambda t: t.depth):
            w.writerow([t.name, f"{t.depth:g}", t.color])


def zones_from_tops(tops: list[Top], bottom: float) -> list[Zone]:
    """Each top starts a zone that ends at the next top (or at the bottom of the log)."""
    ordered = sorted(tops, key=lambda t: t.depth)
    zones = []
    for i, t in enumerate(ordered):
        base = ordered[i + 1].depth if i + 1 < len(ordered) else bottom
        if base > t.depth:
            zones.append(Zone(t.name, t.depth, base))
    return zones


def _column(header: list[str], names: tuple[str, ...], default: int) -> int:
    found = find_column(header, names)
    return default if found is None else found
