"""Familias de curvas: alias de mnemónicos, escalas y colores por defecto.

Cada compañía de servicio usa nombres distintos para la misma medición (GR, SGR, GRC…).
Agrupándolos en familias, una plantilla hecha para un pozo funciona en otro.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from innopetrol.model.layout import CurveStyle, FillSpec, LogLayout, TrackSpec
from innopetrol.model.scales import log_decades, nice_linear_range


@dataclass(frozen=True)
class Family:
    key: str
    name: str  # nombre en español para la UI
    aliases: tuple[str, ...]
    left: float | None = None
    right: float | None = None
    log: bool = False
    color: str = "#000000"
    style: str = "solid"


FAMILIES: dict[str, Family] = {f.key: f for f in [
    Family("gamma_ray", "Rayos gamma", ("GR", "SGR", "CGR", "GRC", "HGR", "ECGR", "GRD", "GAM", "GR_EDTC",
                                         "HSGR", "GRGC", "GRS", "GRN"), 0, 150, color="#1e8449"),
    Family("sp", "Potencial espontáneo", ("SP", "SPBR", "SPC", "SPR"), color="#1f3a93"),
    Family("caliper", "Caliper", ("CALI", "CAL", "HCAL", "CALS", "C1", "CAL1", "CALX", "CALY", "LCAL"),
           6, 16, color="#5d6d7e", style="dash"),
    Family("bit_size", "Diámetro de broca", ("BS", "BIT"), 6, 16, color="#5d6d7e", style="dot"),
    Family("deep_res", "Resistividad profunda", ("LLD", "ILD", "RT", "AT90", "RLA5", "HDRS", "RD", "RILD",
                                                 "M2R9", "RDEP", "AHT90", "HLLD", "RLLD"),
           0.2, 2000, log=True, color="#000000"),
    Family("medium_res", "Resistividad media", ("LLS", "ILM", "AT30", "RLA3", "HMRS", "RM", "M2R3", "RMED",
                                                "AHT30", "HLLS", "RLLS"),
           0.2, 2000, log=True, color="#c0392b", style="dash"),
    Family("shallow_res", "Resistividad somera", ("MSFL", "MSFLC", "SFLU", "SFL", "RXO", "AT10", "LL8", "RXOZ",
                                                  "MLL", "RXO8", "AHT10", "RSHAL"),
           0.2, 2000, log=True, color="#2471a3", style="dot"),
    Family("density", "Densidad", ("RHOB", "RHOZ", "DEN", "ZDEN", "RHO8", "DENS", "HROM", "RHOM"),
           1.95, 2.95, color="#c0392b"),
    Family("density_corr", "Corrección de densidad", ("DRHO", "HDRA", "ZCOR", "DCOR"),
           -0.25, 0.25, color="#a6acaf", style="dot"),
    Family("neutron", "Neutrón", ("NPHI", "TNPH", "NPOR", "CNC", "NPHS", "CN", "NEU", "APLC", "NPLS",
                                  "CNCF", "HNPO", "NPHZ"), 0.45, -0.15, color="#2471a3", style="dash"),
    Family("pef", "Factor fotoeléctrico", ("PEF", "PE", "PEFZ", "PEF8", "HPEF"), 0, 10, color="#7d3c98"),
    Family("sonic", "Sónico", ("DT", "DTC", "DTCO", "DTLN", "AC", "DT4P", "DTL", "DTCM"),
           140, 40, color="#7d3c98"),
    Family("porosity_density", "Porosidad densidad", ("DPHI", "PHID", "DPHZ", "DPOR"),
           0.45, -0.15, color="#c0392b"),
    Family("effective_porosity", "Porosidad efectiva", ("PHIE", "PHI", "PHIT", "POR"), 0.5, 0,
           color="#1f618d"),
    Family("vsh", "Volumen de arcilla", ("VSH", "VCL", "VSHALE", "VCLAY", "VSHGR"), 0, 1, color="#7e5109"),
    Family("sw", "Saturación de agua", ("SW", "SWE", "SWT", "SWA", "SWU"), 1, 0, color="#17202a",
           style="dash"),
    Family("permeability", "Permeabilidad", ("PERM", "K", "PERMCORE", "KCORE", "KINT", "KLOG"),
           0.01, 10000, log=True, color="#117864"),
]}

_ALIAS_INDEX = {alias: fam.key for fam in FAMILIES.values() for alias in fam.aliases}


def family_of(mnemonic: str) -> str | None:
    """Familia de un mnemónico: coincidencia exacta y luego la parte antes de '_' o ':'."""
    m = mnemonic.strip().upper()
    if m in _ALIAS_INDEX:
        return _ALIAS_INDEX[m]
    for sep in ("_", ":", "."):
        base = m.split(sep)[0]
        if base and base in _ALIAS_INDEX:
            return _ALIAS_INDEX[base]
    return None


def find_curve(well, family: str) -> str | None:
    """Primera curva del pozo (con datos) que pertenece a la familia."""
    for mnem, curve in well.curves.items():
        if family_of(mnem) == family and curve.has_data:
            return mnem
    return None


def default_scale(well, mnemonic: str, family: str | None = None) -> tuple[float, float, bool]:
    """Escala (izq, der, log) por defecto: la de la familia, o una 'redonda' según los datos."""
    curve = well.curves.get(mnemonic)
    family = family or family_of(mnemonic)
    fam = FAMILIES.get(family) if family else None
    if fam and fam.left is not None and fam.right is not None:
        left, right = fam.left, fam.right
        # Neutrón y porosidades a veces vienen en % (0–45) en lugar de fracción (0–0.45).
        if fam.key in ("neutron", "porosity_density", "effective_porosity") and curve is not None:
            unit = curve.unit.upper()
            if "%" in unit or unit in ("PU", "P.U.") or (curve.has_data and np.nanpercentile(curve.values, 95) > 1.5):
                left, right = left * 100, right * 100
        return left, right, fam.log
    if curve is None or not curve.has_data:
        return 0.0, 1.0, False
    lo, hi = curve.min, curve.max
    if lo > 0 and hi / lo > 100:
        dl, dr = log_decades(lo, hi)
        return dl, dr, True
    p_lo, p_hi = np.nanpercentile(curve.values, [1, 99])
    nl, nr = nice_linear_range(float(p_lo), float(p_hi))
    return nl, nr, False


def resolve_curve(well, style: CurveStyle) -> str | None:
    """Mnemónico real en el pozo para un estilo de plantilla (por nombre o por familia)."""
    if style.mnemonic in well.curves:
        return style.mnemonic
    if style.family:
        return find_curve(well, style.family)
    fam = family_of(style.mnemonic)
    return find_curve(well, fam) if fam else None


def make_curve_style(well, mnemonic: str) -> CurveStyle:
    fam_key = family_of(mnemonic)
    fam = FAMILIES.get(fam_key) if fam_key else None
    left, right, log = default_scale(well, mnemonic, fam_key)
    return CurveStyle(
        mnemonic=mnemonic,
        family=fam_key,
        color=fam.color if fam else _auto_color(mnemonic),
        style=fam.style if fam else "solid",
        width=1.5 if fam_key in ("gamma_ray", "deep_res", "density") else 1.0,
        left=left,
        right=right,
        log=log,
    )


_GROUPS = [
    ("Correlación", ("gamma_ray", "sp", "caliper", "bit_size")),
    ("Resistividad", ("deep_res", "medium_res", "shallow_res")),
    ("Densidad - Neutrón", ("density", "neutron", "porosity_density")),
    ("Sónico / PEF", ("sonic", "pef", "density_corr")),
    ("Petrofísica", ("vsh", "effective_porosity", "sw")),
    ("Permeabilidad", ("permeability",)),
]


def build_triple_combo(well) -> LogLayout:
    """Layout automático tipo 'triple combo' con las curvas que tenga el pozo."""
    tracks: list[TrackSpec] = []
    used: set[str] = set()
    for title, fams in _GROUPS:
        curves = []
        for mnem, curve in well.curves.items():
            fam = family_of(mnem)
            if fam in fams and curve.has_data:
                curves.append(make_curve_style(well, mnem))
                used.add(mnem)
        if not curves:
            continue
        curves.sort(key=lambda c: fams.index(c.family))
        track = TrackSpec(title=title, curves=curves, width=200 if len(curves) > 1 else 170)
        _add_standard_fills(track)
        tracks.append(track)

    others = [m for m, c in well.curves.items() if m not in used and c.has_data]
    for i in range(0, min(len(others), 8), 4):
        tracks.append(TrackSpec(title="Otras curvas",
                                curves=[make_curve_style(well, m) for m in others[i:i + 4]]))

    depth = TrackSpec(kind="depth", title="Prof.", width=72)
    tracks.insert(1 if tracks else 0, depth)
    return LogLayout(tracks)


def _add_standard_fills(track: TrackSpec) -> None:
    by_fam = {c.family: c for c in track.curves}
    gr = by_fam.get("gamma_ray")
    if gr:
        cutoff = 75.0
        track.fills.append(FillSpec(left_curve=gr.mnemonic, right_value=cutoff, color="#f4d03f",
                                    pattern="dense3", label="Arena"))
        track.fills.append(FillSpec(left_value=cutoff, right_curve=gr.mnemonic, color="#8d6e63",
                                    pattern="dense2", label="Arcilla"))
    rhob, nphi = by_fam.get("density"), by_fam.get("neutron")
    if rhob and nphi:
        track.fills.append(FillSpec(left_curve=rhob.mnemonic, right_curve=nphi.mnemonic, color="#f1c40f",
                                    label="Cruce (posible gas)"))
        track.fills.append(FillSpec(left_curve=nphi.mnemonic, right_curve=rhob.mnemonic, color="#95a5a6",
                                    pattern="dense5", label="Separación (arcilla)"))
    vsh = by_fam.get("vsh")
    if vsh:
        track.fills.append(FillSpec(left_value=vsh.left if vsh.left is not None else 0, right_curve=vsh.mnemonic,
                                    color="#a0522d", pattern="dense3", label="Vsh"))


def _auto_color(mnemonic: str) -> str:
    colors = ["#c0392b", "#2471a3", "#1e8449", "#7d3c98", "#b9770e", "#117a65", "#2e4053"]
    h = sum(ord(c) for c in mnemonic)
    return colors[h % len(colors)]

