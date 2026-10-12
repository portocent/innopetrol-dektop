"""Tracks that show petrophysics results, and where they go in a layout."""

from __future__ import annotations

from innopetrol.i18n import _
from innopetrol.model.layout import CurveStyle, FillSpec, LogLayout, TrackSpec
from innopetrol.model.mnemonics import build_volumes_track, make_curve_style

# (line, fill) of each flag curve shown in the flags track.
_FLAG_COLORS = {
    "RES_FLAG": ("#27ae60", "#82e0aa"),
    "PAY_FLAG": ("#c0392b", "#e74c3c"),
    "BADHOLE": ("#7f8c8d", "#aab7b8"),
}


def results_tracks(well, names: list[str]) -> list[TrackSpec]:
    """Tracks for computed curves: Vsh/φe/Sw, the reservoir/pay flags and the volumes, as available."""
    tracks = []
    styles = [make_curve_style(well, m) for m in ("VSH", "PHIE", "SW") if m in names]
    if styles:
        track = TrackSpec(title=_("Petrophysical results"), width=220, curves=styles)
        if "VSH" in names:
            track.fills.append(
                FillSpec(left_value=0, right_curve="VSH", color="#a0522d", pattern="dense3", label="Vsh")
            )
        if "PHIE" in names:
            track.fills.append(FillSpec(left_curve="PHIE", right_value=0, color="#5dade2", pattern="solid", label="φe"))
        tracks.append(track)
    flags = [m for m in _FLAG_COLORS if m in names]
    if flags:
        flag_track = TrackSpec(title=_("Net res / pay"), width=70, grid="none")
        for m in flags:
            line, fill = _FLAG_COLORS[m]
            flag_track.curves.append(CurveStyle(m, color=line, left=0, right=1, visible=False))
            label = {"RES_FLAG": _("Reservoir"), "PAY_FLAG": _("Pay"), "BADHOLE": _("Bad hole")}[m]
            flag_track.fills.append(FillSpec(left_value=0, right_curve=m, color=fill, label=label))
        tracks.append(flag_track)
    volumes = build_volumes_track(well)
    if volumes is not None:
        tracks.append(volumes)
    return tracks


def _owned(track: TrackSpec) -> set[str]:
    return {c.mnemonic for c in track.curves}


def _find(layout: LogLayout, kind: str, mnemonics=(), families=()) -> int | None:
    """First track of a kind containing one of the curves or families.

    Tracks are found by their curves, never by title: titles depend on the language that was
    active when the layout was created.
    """
    for i, t in enumerate(layout.tracks):
        if t.kind == kind and any(c.mnemonic in mnemonics or (c.family and c.family in families) for c in t.curves):
            return i
    return None


def place_tracks(layout: LogLayout, new_tracks: list[TrackSpec]) -> None:
    """Replaces existing result tracks or inserts the new ones after the density-neutron track
    (or resistivity, or at the end), keeping their order, so they are visible right away."""
    anchor = _find(layout, "curves", families=("density", "neutron"))
    if anchor is None:
        anchor = _find(layout, "curves", families=("deep_res",))
    if anchor is None:
        anchor = len(layout.tracks) - 1
    for track in new_tracks:
        idx = _find(layout, track.kind, mnemonics=_owned(track))
        if idx is None:
            anchor += 1
            layout.tracks.insert(anchor, track)
        else:
            layout.tracks[idx] = track
            anchor = idx
