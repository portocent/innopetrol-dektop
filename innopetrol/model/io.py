"""Opening well files of any supported format."""

from __future__ import annotations

from pathlib import Path

from innopetrol.model import dlis
from innopetrol.model.well import Well

LAS_SUFFIXES = (".las",)


def is_well_file(path: str | Path) -> bool:
    return Path(path).suffix.lower() in LAS_SUFFIXES + dlis.DLIS_SUFFIXES


def load_wells(path: str | Path) -> list[Well]:
    """All wells in a file: one for LAS, one per depth frame for DLIS."""
    if Path(path).suffix.lower() in dlis.DLIS_SUFFIXES:
        return dlis.load_dlis(path)
    return [Well.from_las(path)]


def load_well(path: str | Path, source: str | None = None) -> Well:
    """A single well; for multi-frame files `source` selects the frame (first one if missing)."""
    wells = load_wells(path)
    if source is not None:
        for w in wells:
            if w.source == source:
                return w
    return wells[0]
