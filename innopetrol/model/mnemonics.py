"""Curve families: mnemonic aliases, default scales and colors.

Each service company uses different names for the same measurement (GR, SGR, GRC…).
Grouping them into families lets a template made for one well work on another.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import numpy as np

from innopetrol.i18n import N_, _, pgettext
from innopetrol.model import units
from innopetrol.model.layout import CurveStyle, FillSpec, LogLayout, TrackSpec
from innopetrol.model.scales import log_decades, nice_linear_range


@dataclass(frozen=True)
class Family:
    key: str
    name: str  # display name, translated with _() when shown
    aliases: tuple[str, ...]
    left: float | None = None
    right: float | None = None
    log: bool = False
    color: str = "#000000"
    style: str = "solid"
    unit: str | None = None  # unit of the default left/right scale (converted to the curve's unit)


# Unit in which each family's default scale is written.
_FAMILY_UNITS = {
    "caliper": "in",
    "bit_size": "in",
    "density": "g/cm3",
    "density_corr": "g/cm3",
    "neutron": "v/v",
    "sonic": "us/ft",
    "porosity_density": "v/v",
    "effective_porosity": "v/v",
    "vsh": "v/v",
    "sw": "v/v",
    "matrix_volume": "v/v",
    "bvw": "v/v",
    "bvh": "v/v",
}


FAMILIES: dict[str, Family] = {
    f.key: f
    for f in [
        Family(
            "gamma_ray",
            N_("Gamma ray"),
            ("GR", "SGR", "CGR", "GRC", "HGR", "ECGR", "GRD", "GAM", "GR_EDTC", "HSGR", "GRGC", "GRS", "GRN"),
            0,
            150,
            color="#1e8449",
        ),
        Family("sp", N_("Spontaneous potential"), ("SP", "SPBR", "SPC", "SPR"), color="#1f3a93"),
        Family(
            "caliper",
            N_("Caliper"),
            ("CALI", "CAL", "HCAL", "CALS", "C1", "CAL1", "CALX", "CALY", "LCAL"),
            6,
            16,
            color="#5d6d7e",
            style="dash",
        ),
        Family("bit_size", N_("Bit size"), ("BS", "BIT"), 6, 16, color="#5d6d7e", style="dot"),
        Family(
            "deep_res",
            N_("Deep resistivity"),
            ("LLD", "ILD", "RT", "AT90", "RLA5", "HDRS", "RD", "RILD", "M2R9", "RDEP", "AHT90", "HLLD", "RLLD"),
            0.2,
            2000,
            log=True,
            color="#000000",
        ),
        Family(
            "medium_res",
            N_("Medium resistivity"),
            ("LLS", "ILM", "AT30", "RLA3", "HMRS", "RM", "M2R3", "RMED", "AHT30", "HLLS", "RLLS"),
            0.2,
            2000,
            log=True,
            color="#c0392b",
            style="dash",
        ),
        Family(
            "shallow_res",
            N_("Shallow resistivity"),
            ("MSFL", "MSFLC", "SFLU", "SFL", "RXO", "AT10", "LL8", "RXOZ", "MLL", "RXO8", "AHT10", "RSHAL"),
            0.2,
            2000,
            log=True,
            color="#2471a3",
            style="dot",
        ),
        Family(
            "density",
            N_("Density"),
            ("RHOB", "RHOZ", "DEN", "ZDEN", "RHO8", "DENS", "HROM", "RHOM"),
            1.95,
            2.95,
            color="#c0392b",
        ),
        Family(
            "density_corr",
            N_("Density correction"),
            ("DRHO", "HDRA", "ZCOR", "DCOR"),
            -0.25,
            0.25,
            color="#a6acaf",
            style="dot",
        ),
        Family(
            "neutron",
            N_("Neutron"),
            ("NPHI", "TNPH", "NPOR", "CNC", "NPHS", "CN", "NEU", "APLC", "NPLS", "CNCF", "HNPO", "NPHZ"),
            0.45,
            -0.15,
            color="#2471a3",
            style="dash",
        ),
        Family("pef", N_("Photoelectric factor"), ("PEF", "PE", "PEFZ", "PEF8", "HPEF"), 0, 10, color="#7d3c98"),
        Family(
            "sonic", N_("Sonic"), ("DT", "DTC", "DTCO", "DTLN", "AC", "DT4P", "DTL", "DTCM"), 140, 40, color="#7d3c98"
        ),
        Family(
            "porosity_density", N_("Density porosity"), ("DPHI", "PHID", "DPHZ", "DPOR"), 0.45, -0.15, color="#c0392b"
        ),
        Family("effective_porosity", N_("Effective porosity"), ("PHIE", "PHI", "PHIT", "POR"), 0.5, 0, color="#1f618d"),
        Family("vsh", N_("Shale volume"), ("VSH", "VCL", "VSHALE", "VCLAY", "VSHGR"), 0, 1, color="#7e5109"),
        Family("sw", N_("Water saturation"), ("SW", "SWE", "SWT", "SWA", "SWU"), 1, 0, color="#17202a", style="dash"),
        Family(
            "permeability",
            N_("Permeability"),
            ("PERM", "K", "PERMCORE", "KCORE", "KINT", "KLOG"),
            0.01,
            10000,
            log=True,
            color="#117864",
        ),
        # Separate families: a template must never take water volume for hydrocarbon volume.
        Family("matrix_volume", N_("Matrix volume"), ("VMAT", "VMATRIX"), 0, 1, color="#b7950b"),
        Family("bvw", N_("Bulk volume water"), ("BVW", "BVWE", "BVWT"), 0.5, 0, color="#2471a3"),
        Family("bvh", N_("Bulk volume hydrocarbon"), ("BVH", "BVHC"), 0.5, 0, color="#1e8449"),
        Family(
            "temperature",
            N_("Temperature"),
            ("TEMP", "BHT", "MTEM", "MTEMP", "TEMPC", "TMP", "HTEM", "TFORM"),
            color="#c0392b",
        ),
    ]
}
FAMILIES = {k: dataclasses.replace(f, unit=_FAMILY_UNITS.get(k)) for k, f in FAMILIES.items()}

ALIASES_FORMAT = "innopetrol-aliases"


def normalize_alias(text: str) -> str:
    return text.strip().upper()


class AliasRegistry:
    """Mnemonic → family lookup: the built-in aliases plus the user's (company's) own.

    A user alias wins over a built-in one, so a mnemonic can also be moved to another family.
    The program uses a single shared instance, `ALIASES`.
    """

    def __init__(self, families: dict[str, Family]):
        self._families = families
        self._builtin = {alias: fam.key for fam in families.values() for alias in fam.aliases}
        self._index = dict(self._builtin)
        self._user: dict[str, list[str]] = {}

    def set_user(self, aliases: dict[str, list[str]]) -> None:
        """Replaces the user aliases. Unknown families and empty names are ignored."""
        clean = {
            fam: sorted({normalize_alias(a) for a in names if normalize_alias(a)})
            for fam, names in aliases.items()
            if fam in self._families
        }
        self._user = {fam: names for fam, names in clean.items() if names}
        self._index = dict(self._builtin)
        for fam, names in self._user.items():
            for alias in names:
                self._index[alias] = fam

    def user(self) -> dict[str, list[str]]:
        return {fam: list(names) for fam, names in self._user.items()}

    def family_of(self, mnemonic: str) -> str | None:
        """Exact match first, then the part before '_', ':' or '.' (GR_EDTC → GR)."""
        m = mnemonic.strip().upper()
        if m in self._index:
            return self._index[m]
        for sep in ("_", ":", "."):
            base = m.split(sep)[0]
            if base and base in self._index:
                return self._index[base]
        return None


ALIASES = AliasRegistry(FAMILIES)


def set_user_aliases(aliases: dict[str, list[str]]) -> None:
    ALIASES.set_user(aliases)


def user_aliases() -> dict[str, list[str]]:
    return ALIASES.user()


def alias_conflicts(aliases: dict[str, list[str]]) -> list[tuple[str, list[str]]]:
    """Aliases written in more than one family: (alias, families)."""
    seen: dict[str, list[str]] = {}
    for fam, names in aliases.items():
        for alias in {normalize_alias(a) for a in names if normalize_alias(a)}:
            seen.setdefault(alias, []).append(fam)
    return sorted((a, fams) for a, fams in seen.items() if len(fams) > 1)


def aliases_to_json(aliases: dict[str, list[str]]) -> str:
    import json

    return json.dumps({"format": ALIASES_FORMAT, "version": 1, "aliases": aliases}, indent=2, ensure_ascii=False)


def aliases_from_json(text: str) -> dict[str, list[str]]:
    """Reads an aliases file. Raises ValueError if it is not one."""
    import json

    data = json.loads(text)
    if not isinstance(data, dict) or data.get("format") != ALIASES_FORMAT or not isinstance(data.get("aliases"), dict):
        raise ValueError(_("the file is not an InnoPetrol mnemonic aliases file"))
    return {str(fam): [str(a) for a in names] for fam, names in data["aliases"].items() if isinstance(names, list)}


def family_of(mnemonic: str) -> str | None:
    """Family of a mnemonic (gamma_ray, density…), or None if it is not recognized."""
    return ALIASES.family_of(mnemonic)


def find_curve(well, family: str) -> str | None:
    """First curve of the well (with data) that belongs to the family."""
    for mnem, curve in well.curves.items():
        if family_of(mnem) == family and curve.has_data:
            return mnem
    return None


def default_scale(well, mnemonic: str, family: str | None = None) -> tuple[float, float, bool]:
    """Default (left, right, log) scale: the family's, or a 'round' one derived from the data."""
    curve = well.curves.get(mnemonic)
    family = family or family_of(mnemonic)
    fam = FAMILIES.get(family) if family else None
    if fam and fam.left is not None and fam.right is not None:
        left, right = fam.left, fam.right
        curve_unit = data_unit(curve, fam.unit) if curve is not None else fam.unit
        if fam.unit and curve_unit and curve_unit != fam.unit:
            left, right = (float(v) for v in units.convert([left, right], fam.unit, curve_unit))
        return _clean(left), _clean(right), fam.log
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
    """Actual mnemonic in the well for a template curve style (by name or by family)."""
    if style.mnemonic in well.curves:
        return style.mnemonic
    if style.family:
        return find_curve(well, style.family)
    fam = family_of(style.mnemonic)
    return find_curve(well, fam) if fam else None


def data_unit(curve, expected: str | None = None) -> str | None:
    """Canonical unit of a curve's stored values.

    Uses the unit written in the file, checked against the values for the two common mistakes:
    porosity in % (95th percentile above 1.5) and density in kg/m³ (median above 100), whether
    the unit is missing, unknown or wrongly declared.
    """
    key = units.normalize(curve.unit)
    if (
        expected is None
        or not curve.has_data
        or (key is not None and units.UNITS[key].dimension != units.UNITS[expected].dimension)
    ):
        return key
    # Values that are physically impossible in the declared unit win over the label
    # (files labeled "DEC" with porosity 0–45 are common).
    if expected == "v/v" and key in (None, "v/v") and np.nanpercentile(curve.values, 95) > 1.5:
        return "%"
    if expected == "g/cm3" and key in (None, "g/cm3") and np.nanmedian(curve.values) > 100:
        return "kg/m3"
    return key or expected


def _clean(v: float) -> float:
    return float(f"{v:.6g}")


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
        unit=well.curves[mnemonic].unit if mnemonic in well.curves else None,
    )


_GROUPS = [
    (N_("Correlation"), ("gamma_ray", "sp", "caliper", "bit_size")),
    (N_("Resistivity"), ("deep_res", "medium_res", "shallow_res")),
    (N_("Density - Neutron"), ("density", "neutron", "porosity_density")),
    (N_("Sonic / PEF"), ("sonic", "pef", "density_corr")),
    (N_("Petrophysics"), ("vsh", "effective_porosity", "sw")),
    (N_("Permeability"), ("permeability",)),
]


def build_triple_combo(well) -> LogLayout:
    """Automatic 'triple combo' style layout with whatever curves the well has.

    Titles and labels are created in the active interface language.
    """
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
        track = TrackSpec(title=_(title), curves=curves, width=200 if len(curves) > 1 else 170)
        _add_standard_fills(track)
        tracks.append(track)
        if fams[0] == "vsh":
            volumes = build_volumes_track(well)
            if volumes is not None:
                tracks.append(volumes)
                used.update(c.mnemonic for c in volumes.curves)

    others = [m for m, c in well.curves.items() if m not in used and c.has_data]
    for i in range(0, min(len(others), 8), 4):
        tracks.append(TrackSpec(title=_("Other curves"), curves=[make_curve_style(well, m) for m in others[i : i + 4]]))

    depth = TrackSpec(kind="depth", title=pgettext("track title", "Depth"), width=72)
    tracks.insert(1 if tracks else 0, depth)
    return LogLayout(tracks)


# Components of the volumes track, left to right, with their usual colors.
VOLUME_COMPONENTS = (("VSH", "#a1887f"), ("VMAT", "#f7dc6f"), ("BVH", "#27ae60"), ("BVW", "#5dade2"))
# Names shown in the volumes track header.
VOLUME_LABELS = {
    "VSH": N_("Shale"),
    "VCL": N_("Clay"),
    "VMAT": N_("Matrix"),
    "BVH": N_("Hydrocarbon"),
    "BVW": N_("Water"),
    "PHIE": N_("Porosity"),
    "PHIT": N_("Porosity"),
}


def build_volumes_track(well) -> TrackSpec | None:
    """Stacked shale / matrix / hydrocarbon / water track from the petrophysics results.

    Without saturation the porosity is shown as one component. None if Vsh and porosity are missing.
    """
    names = [m for m, _color in VOLUME_COMPONENTS if m in well.curves]
    if not {"VSH", "VMAT"} <= set(names):
        return None
    components = [(m, c) for m, c in VOLUME_COMPONENTS if m in names]
    if "BVW" not in names and "PHIE" in well.curves:
        components.append(("PHIE", "#aed6f1"))
    curves = [
        CurveStyle(
            m,
            family=family_of(m),
            color=c,
            left=0,
            right=1,
            unit=units.normalize(well.curves[m].unit) or well.curves[m].unit,
        )
        for m, c in components
    ]
    return TrackSpec(kind="volumes", title=_("Volumes"), width=150, grid="none", curves=curves)


def _add_standard_fills(track: TrackSpec) -> None:
    by_fam = {c.family: c for c in track.curves}
    gr = by_fam.get("gamma_ray")
    if gr:
        cutoff = 75.0
        track.fills.append(
            FillSpec(left_curve=gr.mnemonic, right_value=cutoff, color="#f4d03f", pattern="dense3", label=_("Sand"))
        )
        track.fills.append(
            FillSpec(left_value=cutoff, right_curve=gr.mnemonic, color="#8d6e63", pattern="dense2", label=_("Shale"))
        )
    rhob, nphi = by_fam.get("density"), by_fam.get("neutron")
    if rhob and nphi:
        track.fills.append(
            FillSpec(
                left_curve=rhob.mnemonic,
                right_curve=nphi.mnemonic,
                color="#f1c40f",
                label=_("Crossover (possible gas)"),
            )
        )
        track.fills.append(
            FillSpec(
                left_curve=nphi.mnemonic,
                right_curve=rhob.mnemonic,
                color="#95a5a6",
                pattern="dense5",
                label=_("Separation (shale)"),
            )
        )
    vsh = by_fam.get("vsh")
    if vsh:
        track.fills.append(
            FillSpec(
                left_value=vsh.left if vsh.left is not None else 0,
                right_curve=vsh.mnemonic,
                color="#a0522d",
                pattern="dense3",
                label="Vsh",
            )
        )


def _auto_color(mnemonic: str) -> str:
    colors = ["#c0392b", "#2471a3", "#1e8449", "#7d3c98", "#b9770e", "#117a65", "#2e4053"]
    h = sum(ord(c) for c in mnemonic)
    return colors[h % len(colors)]
