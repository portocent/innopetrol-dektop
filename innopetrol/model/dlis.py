"""DLIS reading (the binary format most service companies deliver logs in).

A DLIS file holds one or more logical files, each with frames: groups of channels sampled
against a common index (e.g. a 6-inch main frame and a high-resolution frame). Each depth-indexed
frame becomes one Well. Array channels (images, waveforms) are not supported yet and are listed
in the well's notes.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import numpy as np

from innopetrol.i18n import _, ngettext
from innopetrol.model.well import Curve, HeaderItem, Well, clean_samples, elevation_from_header, unique_mnemonic

DLIS_SUFFIXES = (".dlis", ".dls")
# Depth units seen in DLIS index channels -> (factor, unit used by the program).
_UNIT_RE = re.compile(r"^\s*([0-9.]+)?\s*([a-zA-Z]+)\s*$")
_BASE_UNITS = {
    "m": (1.0, "m"),
    "meter": (1.0, "m"),
    "meters": (1.0, "m"),
    "metre": (1.0, "m"),
    "cm": (0.01, "m"),
    "mm": (0.001, "m"),
    "dm": (0.1, "m"),
    "km": (1000.0, "m"),
    "ft": (1.0, "ft"),
    "f": (1.0, "ft"),
    "feet": (1.0, "ft"),
    "foot": (1.0, "ft"),
    "in": (1 / 12, "ft"),
    "inch": (1 / 12, "ft"),
}
_DEPTH_INDEX_TYPES = {"BOREHOLE-DEPTH", "VERTICAL-DEPTH", "DEPTH"}


def available() -> bool:
    try:
        import dlisio  # noqa: F401
    except ImportError:
        return False
    return True


def depth_unit_factor(unit: str) -> tuple[float, str] | None:
    """('0.1 in') -> (1/120, 'ft'); None if the unit is not a length."""
    m = _UNIT_RE.match(unit or "")
    if not m:
        return None
    base = _BASE_UNITS.get(m.group(2).lower())
    if base is None:
        return None
    scale = float(m.group(1)) if m.group(1) else 1.0
    return scale * base[0], base[1]


def load_dlis(path: str | Path) -> list[Well]:
    """All depth-indexed frames of a DLIS file, one Well per frame."""
    if not available():
        raise ValueError(_("DLIS support is not available on this platform (the dlisio package is not installed)"))
    from dlisio import common, dlis

    path = Path(path)
    logging.getLogger("dlisio").setLevel(logging.ERROR)
    common.set_encodings(["utf-8", "latin-1"])  # vendor strings outside ASCII
    wells: list[Well] = []
    skipped_frames = []
    with dlis.load(str(path)) as files:
        for lf in files:
            origin = lf.origins[0] if lf.origins else None
            base_name = (origin.well_name if origin else "") or path.stem
            header = _header(origin, lf)
            frames = [fr for fr in lf.frames if fr.index_type in _DEPTH_INDEX_TYPES or fr.index_type is None]
            skipped_frames += [fr.name for fr in lf.frames if fr not in frames]
            for fr in frames:
                well = _frame_to_well(fr, base_name, header, path, single=len(frames) == 1 and len(files) == 1)
                if well is not None:
                    wells.append(well)
    if not wells:
        raise ValueError(_("the file has no depth-indexed data"))
    if skipped_frames:
        wells[0].notes.append(
            _("frames not indexed by depth were skipped: {frames}").format(frames=", ".join(skipped_frames))
        )
    return wells


def _header(origin, lf) -> list[HeaderItem]:
    items = []
    if origin is not None:
        for mnem, value, descr in (
            ("WELL", origin.well_name, "Well"),
            ("FLD", origin.field_name, "Field"),
            ("COMP", origin.company, "Company"),
            ("UWI", origin.well_id, "Well id"),
            ("RUN", origin.run_nr, "Run number"),
            ("SRVC", origin.producer_name, "Service"),
        ):
            if value is not None and str(value).strip() not in ("", "[]", "None"):
                items.append(HeaderItem(mnem, "", str(value), descr))
    for p in lf.parameters:
        try:
            values = p.values
        except Exception:
            continue
        if values is not None and np.size(values) == 1:
            value = np.asarray(values).ravel()[0]
            attr = (p.attributes or {}).get("VALUES")
            units = (getattr(attr, "units", "") or "") if attr is not None else ""
            long_name = p.long_name if isinstance(p.long_name, str) else str(p.long_name or "")
            items.append(
                HeaderItem(p.name, units, str(value.decode() if isinstance(value, bytes) else value), long_name)
            )
    return items


def _frame_to_well(frame, base_name: str, header, path: Path, single: bool) -> Well | None:
    curves_data = frame.curves()
    index_name = frame.index
    index_channel = next((c for c in frame.channels if c.name == index_name), frame.channels[0])
    unit_info = depth_unit_factor(index_channel.units or "")
    if unit_info is None:
        return None
    factor, depth_unit = unit_info
    depth = np.asarray(curves_data[index_name], dtype=float) * factor

    curves: dict[str, Curve] = {}
    arrays = []
    for ch in frame.channels:
        if ch.name == index_name or ch.name not in curves_data.dtype.names:
            continue
        values = np.asarray(curves_data[ch.name])
        if values.ndim != 1:
            arrays.append(f"{ch.name} ({int(np.prod(values.shape[1:]))})")
            continue
        mnem = unique_mnemonic(ch.name, curves)
        curves[mnem] = Curve(
            mnem,
            (ch.units or "").strip(),
            (ch.long_name or "").strip() if isinstance(ch.long_name, str) else str(ch.long_name or ""),
            values.astype(float),
        )
    if not curves:
        return None
    depth, notes = clean_samples(depth, curves)
    if depth.size < 2:
        return None
    if arrays:
        notes.append(
            ngettext(
                "array channel not supported yet, skipped: {channels}",
                "array channels not supported yet, skipped: {channels}",
                len(arrays),
            ).format(channels=", ".join(arrays))
        )
    name = base_name if single else f"{base_name} ({frame.name})"
    return Well(
        name=name,
        path=path,
        depth=depth,
        depth_unit=depth_unit,
        depth_mnemonic=index_name,
        header=list(header),
        curves=curves,
        notes=notes,
        source=frame.name,
        elevation=elevation_from_header(header, depth_unit),
    )
