"""Formation tops (markers) and the zones between them."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

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
    text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = [r for r in csv.reader(text.splitlines(), dialect) if any(c.strip() for c in r)]
    if not rows:
        return []

    head = [c.strip().lower() for c in rows[0]]
    has_header = not _is_number(rows[0][1] if len(rows[0]) > 1 else "")
    if has_header:
        name_i = _find(head, _NAME_COLS, 0)
        depth_i = _find(head, _DEPTH_COLS, 1)
        color_i = _find(head, ("color", "colour"), None)
        well_i = _find(head, _WELL_COLS, None)
        if name_i == depth_i:
            name_i, depth_i = 0, 1
        rows = rows[1:]
    else:
        name_i, depth_i, color_i, well_i = 0, 1, 2, None

    tops = []
    for r in rows:
        if well_i is not None and well_name and well_i < len(r):
            if r[well_i].strip().upper() != well_name.strip().upper():
                continue
        try:
            depth = float(r[depth_i].replace(",", ".") if dialect.delimiter != "," else r[depth_i])
        except (ValueError, IndexError):
            continue
        color = r[color_i].strip() if color_i is not None and color_i < len(r) and r[color_i].strip() else None
        tops.append(Top(r[name_i].strip(), depth, color or PALETTE[len(tops) % len(PALETTE)]))
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


def _find(head: list[str], names: tuple, default):
    for i, h in enumerate(head):
        if h in names:
            return i
    return default


def _is_number(s: str) -> bool:
    try:
        float(s.replace(",", "."))
        return True
    except ValueError:
        return False
