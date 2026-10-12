"""Descripción de cómo se dibuja un pozo: tracks, curvas y rellenos.

Son dataclasses simples que se convierten a/desde dict (JSON). Reemplazan a las clases
`Track`, `Line` y `Grid` originales, que guardaban enums de Qt y se serializaban con pickle.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field, fields

LINE_STYLES = ["solid", "dash", "dashdot", "dot", "dashdotdot"]
LINE_STYLE_NAMES = {"solid": "Continua", "dash": "Guiones", "dashdot": "Guion-punto",
                    "dot": "Puntos", "dashdotdot": "Guion-punto-punto"}
# Mismo orden que los iconos d1…d10 del proyecto original.
FILL_PATTERNS = ["solid", "dense1", "dense2", "dense3", "dense5", "dense6", "hor", "ver", "bdiag", "diagcross"]


@dataclass
class CurveStyle:
    mnemonic: str
    family: str | None = None  # familia (gamma_ray, density…) para que la plantilla sirva en otros pozos
    color: str = "#000000"
    width: float = 1.0
    style: str = "solid"
    left: float | None = None  # None = automático
    right: float | None = None
    log: bool = False
    visible: bool = True


@dataclass
class FillSpec:
    """Relleno entre dos límites. Cada límite es una curva, un valor fijo o el borde del track.

    Se rellena sólo donde el límite izquierdo queda a la izquierda del derecho
    (misma regla que el proyecto original). Los valores fijos se ubican con la escala de
    la curva del otro lado.
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
    """Ignora claves desconocidas: plantillas de versiones futuras no rompen la carga."""
    names = {f.name for f in fields(cls)} - {"curves", "fills"}
    return {k: v for k, v in d.items() if k in names}
