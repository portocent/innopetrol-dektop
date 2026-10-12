"""Depth intervals of a well: perforations, tests, losses, cored intervals, runs and comments.

Stored in measured depth (MD) in the well's depth unit, like tops, and drawn in an "intervals" track.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from innopetrol.i18n import N_
from innopetrol.model.text_tables import find_column, is_number, parse_number, read_rows

# kind -> (display name translated with _(), default color, fill pattern)
KINDS = {
    "perforation": (N_("Perforation"), "#c0392b", "bdiag"),
    "test": (N_("Test (DST)"), "#2471a3", "solid"),
    "loss": (N_("Losses"), "#7d3c98", "dense5"),
    "core": (N_("Cored interval"), "#b9770e", "dense3"),
    "run": (N_("Logging run"), "#566573", "dense6"),
    "comment": (N_("Comment"), "#1e8449", "solid"),
}


@dataclass
class Interval:
    top: float
    base: float
    kind: str = "comment"
    label: str = ""
    color: str = ""  # empty = the kind's color

    def __post_init__(self):
        if self.base < self.top:
            self.top, self.base = self.base, self.top
        if self.kind not in KINDS:
            self.kind = "comment"

    @property
    def shown_color(self) -> str:
        return self.color or KINDS[self.kind][1]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Interval:
        return cls(
            float(d["top"]),
            float(d["base"]),
            str(d.get("kind", "comment")),
            str(d.get("label", "")),
            str(d.get("color", "")),
        )


_TOP_COLS = ("top", "from", "desde", "tope", "techo", "md top", "top md")
_BASE_COLS = ("base", "bottom", "to", "hasta", "base md", "bottom md")
_KIND_COLS = ("kind", "type", "tipo", "clase")
_LABEL_COLS = (
    "label",
    "name",
    "description",
    "comment",
    "etiqueta",
    "nombre",
    "descripcion",
    "descripción",
    "comentario",
)
# Words that identify the kind in a type column (English and Spanish).
_KIND_WORDS = {
    "perforation": ("perf", "punz", "baleo", "cañon", "canon"),
    "test": ("dst", "test", "prueba", "ensayo"),
    "loss": ("loss", "pérdida", "perdida"),
    "core": ("core", "corona", "núcleo", "nucleo"),
    "run": ("run", "corrida", "carrera"),
}


def kind_from_text(text: str) -> str:
    t = text.strip().lower()
    return next((k for k, words in _KIND_WORDS.items() if any(w in t for w in words)), "comment")


def load_intervals_csv(path: str | Path, default_kind: str = "comment") -> list[Interval]:
    """Reads intervals from CSV/TXT: top and base columns, optionally type and label (English or Spanish
    headers). Without a header the columns are: top, base[, label]."""
    rows = read_rows(path)
    if not rows:
        return []
    kind_i: int | None
    label_i: int | None
    if is_number(rows[0][0]):
        top_i, base_i, kind_i, label_i = 0, 1, None, 2
    else:
        head = rows[0]
        top_col, base_col = find_column(head, _TOP_COLS), find_column(head, _BASE_COLS)
        if top_col is None or base_col is None:
            raise ValueError(", ".join(head))
        top_i, base_i = top_col, base_col
        kind_i, label_i = find_column(head, _KIND_COLS), find_column(head, _LABEL_COLS)
        rows = rows[1:]
    out = []
    for r in rows:
        try:
            top, base = parse_number(r[top_i]), parse_number(r[base_i])
        except (ValueError, IndexError):
            continue
        kind = kind_from_text(r[kind_i]) if kind_i is not None and kind_i < len(r) else default_kind
        label = r[label_i] if label_i is not None and label_i < len(r) else ""
        out.append(Interval(top, base, kind, label))
    return sorted(out, key=lambda i: i.top)
