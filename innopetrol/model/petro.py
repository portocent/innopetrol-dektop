"""Petrofísica básica: Vsh, porosidad, saturación de agua (Archie), net pay y resumen por zonas.

Cada resultado se genera como una *fórmula* de la calculadora de curvas, así queda
documentado cómo se obtuvo y se puede recalcular al reabrir un proyecto.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from innopetrol.model.calculator import curve_ref, evaluate
from innopetrol.model.tops import Zone
from innopetrol.model.well import Curve

# ---------------------------------------------------------------- funciones de referencia (numpy)


def gr_index(gr, gr_clean, gr_shale):
    return np.clip((np.asarray(gr, float) - gr_clean) / (gr_shale - gr_clean), 0, 1)


def vsh_larionov_tertiary(igr):
    return 0.083 * (2 ** (3.7 * np.asarray(igr, float)) - 1)


def vsh_larionov_older(igr):
    return 0.33 * (2 ** (2 * np.asarray(igr, float)) - 1)


def phi_density(rhob, rho_ma=2.65, rho_fl=1.0):
    return (rho_ma - np.asarray(rhob, float)) / (rho_ma - rho_fl)


def sw_archie(rt, phi, rw, a=1.0, m=2.0, n=2.0):
    rt, phi = np.asarray(rt, float), np.asarray(phi, float)
    with np.errstate(all="ignore"):
        sw = ((a * rw) / (phi ** m * rt)) ** (1 / n)
    sw = np.where((phi > 0) & (rt > 0), sw, np.nan)
    return np.clip(sw, 0, 1)


# ---------------------------------------------------------------- parámetros y fórmulas

VSH_METHODS = {"linear": "Lineal (IGR)", "larionov_tertiary": "Larionov (rocas terciarias)",
               "larionov_older": "Larionov (rocas antiguas)"}
PHI_METHODS = {"density": "Densidad", "nd_average": "Neutrón-densidad (promedio)",
               "nd_rms": "Neutrón-densidad (RMS, zonas con gas)"}


@dataclass
class PetroParams:
    gr_curve: str | None = None
    gr_clean: float = 20.0
    gr_shale: float = 120.0
    vsh_method: str = "linear"
    rhob_curve: str | None = None
    rho_ma: float = 2.65
    rho_fl: float = 1.0
    nphi_curve: str | None = None
    phi_method: str = "density"
    rt_curve: str | None = None
    rw: float = 0.05
    a: float = 1.0
    m: float = 2.0
    n: float = 2.0
    vsh_cut: float = 0.4
    phi_cut: float = 0.08
    sw_cut: float = 0.6

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> PetroParams:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class FormulaSpec:
    mnemonic: str
    unit: str
    description: str
    formula: str


def _neutron_in_percent(well, mnem: str) -> bool:
    c = well.curves[mnem]
    unit = c.unit.upper()
    return "%" in unit or unit in ("PU", "P.U.") or (c.has_data and np.nanpercentile(c.values, 95) > 1.5)


def build_formulas(well, p: PetroParams) -> list[FormulaSpec]:
    """Fórmulas en orden de dependencia según las curvas de entrada disponibles."""
    out: list[FormulaSpec] = []
    has_vsh = has_phi = False

    if p.gr_curve and p.gr_curve in well.curves:
        igr = f"clip(({curve_ref(p.gr_curve)} - {p.gr_clean:g}) / ({p.gr_shale:g} - {p.gr_clean:g}), 0, 1)"
        vsh = {
            "linear": igr,
            "larionov_tertiary": f"clip(0.083 * (2 ** (3.7 * {igr}) - 1), 0, 1)",
            "larionov_older": f"clip(0.33 * (2 ** (2 * {igr}) - 1), 0, 1)",
        }[p.vsh_method]
        out.append(FormulaSpec("VSH", "v/v", f"Vsh - {VSH_METHODS[p.vsh_method]}", vsh))
        has_vsh = True

    if p.rhob_curve and p.rhob_curve in well.curves:
        phid = f"({p.rho_ma:g} - {curve_ref(p.rhob_curve)}) / ({p.rho_ma:g} - {p.rho_fl:g})"
        if p.phi_method != "density" and p.nphi_curve and p.nphi_curve in well.curves:
            phin = curve_ref(p.nphi_curve)
            if _neutron_in_percent(well, p.nphi_curve):
                phin = f"({phin} / 100)"
            out.append(FormulaSpec("PHID", "v/v", "Porosidad densidad", f"clip({phid}, -0.15, 0.6)"))
            if p.phi_method == "nd_average":
                phit = f"(PHID + {phin}) / 2"
            else:
                phit = f"sqrt((PHID ** 2 + {phin} ** 2) / 2)"
            method = PHI_METHODS[p.phi_method]
        else:
            phit = phid
            method = PHI_METHODS["density"]
        out.append(FormulaSpec("PHIT", "v/v", f"Porosidad total - {method}", f"clip({phit}, 0, 0.6)"))
        phie = "clip(PHIT * (1 - VSH), 0, 0.6)" if has_vsh else "PHIT"
        out.append(FormulaSpec("PHIE", "v/v", "Porosidad efectiva", phie))
        has_phi = True

    if has_phi and p.rt_curve and p.rt_curve in well.curves:
        rt = curve_ref(p.rt_curve)
        sw = (f"where((PHIE > 0) & ({rt} > 0), "
              f"clip((({p.a:g} * {p.rw:g}) / (PHIE ** {p.m:g} * {rt})) ** (1 / {p.n:g}), 0, 1), nan)")
        out.append(FormulaSpec("SW", "v/v", f"Sw Archie (a={p.a:g}, m={p.m:g}, n={p.n:g}, Rw={p.rw:g})", sw))

    if has_phi:
        cond = f"(PHIE >= {p.phi_cut:g})"
        if has_vsh:
            cond = f"(VSH <= {p.vsh_cut:g}) & {cond}"
        out.append(FormulaSpec("RES_FLAG", "", "Bandera de reservorio neto",
                               f"where(isnan(PHIE), nan, where({cond}, 1, 0))"))
        if any(f.mnemonic == "SW" for f in out):
            out.append(FormulaSpec("PAY_FLAG", "", "Bandera de pago neto",
                                   f"where(isnan(SW), nan, where((RES_FLAG > 0) & (SW <= {p.sw_cut:g}), 1, 0))"))
    return out


def compute(well, p: PetroParams) -> list[Curve]:
    """Evalúa las fórmulas; cada resultado queda disponible para la siguiente."""
    env = {m: c.values for m, c in well.curves.items()}
    curves = []
    for spec in build_formulas(well, p):
        values = evaluate(spec.formula, env)
        env[spec.mnemonic] = values
        curves.append(Curve(spec.mnemonic, spec.unit, spec.description, values, formula=spec.formula))
    return curves


# ---------------------------------------------------------------- resumen por zonas


@dataclass
class ZoneSummary:
    zone: str
    top: float
    base: float
    gross: float
    net_reservoir: float
    net_pay: float
    ntg: float
    phi_avg: float
    sw_avg: float
    vsh_avg: float


def sample_thickness(depth: np.ndarray) -> np.ndarray:
    return np.abs(np.gradient(depth))


def zone_summary(well, zones: list[Zone], vsh: str | None, phi: str | None, sw: str | None,
                 vsh_cut: float, phi_cut: float, sw_cut: float) -> list[ZoneSummary]:
    """Espesor bruto, neto de reservorio, neto de pago, N/G y promedios por zona.

    Promedios: φ ponderado por espesor sobre reservorio neto; Sw ponderado por φ·h sobre pago neto.
    """
    h = sample_thickness(well.depth)
    nan = np.full(well.depth.shape, np.nan)
    v = well.curves[vsh].values if vsh in well.curves else nan
    f = well.curves[phi].values if phi in well.curves else nan
    s = well.curves[sw].values if sw in well.curves else nan

    res = np.isfinite(f) & (f >= phi_cut)
    if vsh in well.curves:
        res &= np.isfinite(v) & (v <= vsh_cut)
    pay = res & np.isfinite(s) & (s <= sw_cut)

    out = []
    for z in zones:
        m = well.interval_mask(z.top, z.base)
        gross = float(h[m].sum())
        net_r = float(h[m & res].sum())
        net_p = float(h[m & pay].sum())
        out.append(ZoneSummary(
            zone=z.name, top=z.top, base=z.base, gross=gross, net_reservoir=net_r, net_pay=net_p,
            ntg=net_r / gross if gross else float("nan"),
            phi_avg=_wavg(f, h, m & res),
            sw_avg=_wavg(s, h * np.nan_to_num(f), m & pay),
            vsh_avg=_wavg(v, h, m & res),
        ))
    return out


def _wavg(values, weights, mask) -> float:
    ok = mask & np.isfinite(values)
    w = weights[ok]
    return float(np.sum(values[ok] * w) / np.sum(w)) if ok.any() and np.sum(w) > 0 else float("nan")
