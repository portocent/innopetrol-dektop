"""How a well is drawn: tracks, curves and fills.

Plain dataclasses converted to/from dict (JSON). They replace the original `Track`, `Line` and
`Grid` classes, which stored Qt enums and were serialized with pickle.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field, fields

from innopetrol.i18n import N_

LINE_STYLES = ["solid", "dash", "dashdot", "dot", "dashdotdot"]
# Display names, translated with _() when shown.
LINE_STYLE_NAMES = {"solid": N_("Solid"), "dash": N_("Dashed"), "dashdot": N_("Dash-dot"),
                    "dot": N_("Dotted"), "dashdotdot": N_("Dash-dot-dot")}
# Same order as the d1…d10 icons from the original project.
FILL_PATTERNS = ["solid", "dense1", "dense2", "dense3", "dense5", "dense6", "hor", "ver", "bdiag", "diagcross"]


@dataclass
class CurveStyle:
    mnemonic: str
    family: str | None = None  # family (gamma_ray, density…) so a template works on other wells
    color: str = "#000000"
    width: float = 1.0
    style: str = "solid"
    left: float | None = None  # None = automatic
    right: float | None = None
    log: bool = False
    visible: bool = True
    unit: str | None = None  # unit in which left/right are written (None = the curve's file unit)


@dataclass
class FillSpec:
    """Fill between two bounds. Each bound is a curve, a fixed value or the track edge.

    Only the area where the left bound lies to the left of the right bound is filled
    (same rule as the original project). Fixed values are placed using the scale of the
    curve on the other side.
    """

    left_curve: str | None = None
    left_value: float | None = None
    right_curve: str | None = None
    right_value: float | None = None
    color: str = "#f4d03f"
    pattern: str = "solid"
    label: str = ""
    visible: bool = True


@dataclass
class TrackSpec:
    kind: str = "curves"  # "curves" | "depth"
    title: str = ""
    width: int = 180
    grid: str = "auto"  # "auto" | "linear" | "log" | "none"
    divisions: int = 10
    curves: list[CurveStyle] = field(default_factory=list)
    fills: list[FillSpec] = field(default_factory=list)

    @property
    def is_depth(self) -> bool:
        return self.kind == "depth"


@dataclass
class LogLayout:
    tracks: list[TrackSpec] = field(default_factory=list)

    def copy(self) -> LogLayout:
        return copy.deepcopy(self)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> LogLayout:
        tracks = []
        for t in d.get("tracks", []):
            t = dict(t)
            curves = [CurveStyle(**_known(CurveStyle, c)) for c in t.pop("curves", [])]
            fills = [FillSpec(**_known(FillSpec, f)) for f in t.pop("fills", [])]
            tracks.append(TrackSpec(**_known(TrackSpec, t), curves=curves, fills=fills))
        return cls(tracks)


def _known(cls, d: dict) -> dict:
    """Ignores unknown keys so templates from future versions still load."""
    names = {f.name for f in fields(cls)} - {"curves", "fills"}
    return {k: v for k, v in d.items() if k in names}
