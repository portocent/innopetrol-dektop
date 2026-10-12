"""Basic petrophysics: Vsh, porosity, water saturation (Archie), net pay and zone summaries.

Every result is produced as a curve calculator *formula*, which documents how it was obtained
and lets it be recomputed when a project is reopened.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from innopetrol.i18n import N_, _
from innopetrol.model import units
from innopetrol.model.calculator import curve_ref, evaluate
from innopetrol.model.tops import Zone
from innopetrol.model.well import Curve

# ---------------------------------------------------------------- reference functions (numpy)


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


# ---------------------------------------------------------------- parameters and formulas

# Display names, translated with _() when shown.
VSH_METHODS = {"linear": N_("Linear (IGR)"), "larionov_tertiary": N_("Larionov (tertiary rocks)"),
               "larionov_older": N_("Larionov (older rocks)")}
PHI_METHODS = {"density": N_("Density"), "nd_average": N_("Neutron-density (average)"),
               "nd_rms": N_("Neutron-density (RMS, gas zones)")}


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


def input_ref(well, mnem: str, expected: str) -> str:
    """A curve reference inside a formula, converted to the unit the equation expects.

    The conversion is written into the formula (e.g. `(RHOB * 0.001)` for kg/m³), so stored
    formulas stay correct and readable whatever units the file or the display use.
    """
    from innopetrol.model.mnemonics import data_unit  # local import: mnemonics imports this module's peers

    ref = curve_ref(mnem)
    scale, shift = units.linear_coefficients(data_unit(well.curves[mnem], expected), expected)
    if scale == 1.0 and shift == 0.0:
        return ref
    text = f"{ref} * {scale:.10g}"
    if shift:
        text += f" + {shift:.10g}"
    return f"({text})"


def build_formulas(well, p: PetroParams) -> list[FormulaSpec]:
    """Formulas in dependency order, depending on which input curves are available."""
    out: list[FormulaSpec] = []
    has_vsh = has_phi = False

    if p.gr_curve and p.gr_curve in well.curves:
        igr = f"clip(({curve_ref(p.gr_curve)} - {p.gr_clean:g}) / ({p.gr_shale:g} - {p.gr_clean:g}), 0, 1)"
        vsh = {
            "linear": igr,
            "larionov_tertiary": f"clip(0.083 * (2 ** (3.7 * {igr}) - 1), 0, 1)",
            "larionov_older": f"clip(0.33 * (2 ** (2 * {igr}) - 1), 0, 1)",
        }[p.vsh_method]
        out.append(FormulaSpec("VSH", "v/v", _("Vsh - {method}").format(method=_(VSH_METHODS[p.vsh_method])), vsh))
        has_vsh = True

    if p.rhob_curve and p.rhob_curve in well.curves:
        rhob = input_ref(well, p.rhob_curve, "g/cm3")
        phid = f"({p.rho_ma:g} - {rhob}) / ({p.rho_ma:g} - {p.rho_fl:g})"
        if p.phi_method != "density" and p.nphi_curve and p.nphi_curve in well.curves:
            phin = input_ref(well, p.nphi_curve, "v/v")
            out.append(FormulaSpec("PHID", "v/v", _("Density porosity"), f"clip({phid}, -0.15, 0.6)"))
            if p.phi_method == "nd_average":
                phit = f"(PHID + {phin}) / 2"
            else:
                phit = f"sqrt((PHID ** 2 + {phin} ** 2) / 2)"
            method_key = p.phi_method
        else:
            phit = phid
            method_key = "density"
        method = _(PHI_METHODS[method_key])
        out.append(FormulaSpec("PHIT", "v/v", _("Total porosity - {method}").format(method=method), f"clip({phit}, 0, 0.6)"))
        phie = "clip(PHIT * (1 - VSH), 0, 0.6)" if has_vsh else "PHIT"
        out.append(FormulaSpec("PHIE", "v/v", _("Effective porosity"), phie))
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
        out.append(FormulaSpec("RES_FLAG", "", _("Net reservoir flag"),
                               f"where(isnan(PHIE), nan, where({cond}, 1, 0))"))
        if any(f.mnemonic == "SW" for f in out):
            out.append(FormulaSpec("PAY_FLAG", "", _("Net pay flag"),
                                   f"where(isnan(SW), nan, where((RES_FLAG > 0) & (SW <= {p.sw_cut:g}), 1, 0))"))
    return out


def compute(well, p: PetroParams) -> list[Curve]:
    """Evaluates the formulas; each result is available to the following ones."""
    env = {m: c.values for m, c in well.curves.items()}
    curves = []
    for spec in build_formulas(well, p):
        values = evaluate(spec.formula, env)
        env[spec.mnemonic] = values
        curves.append(Curve(spec.mnemonic, spec.unit, spec.description, values, formula=spec.formula))
    return curves


# ---------------------------------------------------------------- zone summary


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
    """Gross, net reservoir and net pay thickness, N/G and averages per zone.

    Averages: φ weighted by thickness over net reservoir; Sw weighted by φ·h over net pay.
    """
    h = sample_thickness(well.depth)
    nan = np.full(well.depth.shape, np.nan)
    v = _as_fraction(well, vsh, nan)
    f = _as_fraction(well, phi, nan)
    s = _as_fraction(well, sw, nan)

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


def _as_fraction(well, mnem: str | None, default: np.ndarray) -> np.ndarray:
    """Values of a volume curve (porosity, Sw, Vsh) as a fraction, whatever unit it comes in."""
    if mnem not in well.curves:
        return default
    from innopetrol.model.mnemonics import data_unit

    curve = well.curves[mnem]
    unit = data_unit(curve, "v/v")
    return units.convert(curve.values, unit, "v/v") if unit in ("%", "v/v") else curve.values


def _wavg(values, weights, mask) -> float:
    ok = mask & np.isfinite(values)
    w = weights[ok]
    return float(np.sum(values[ok] * w) / np.sum(w)) if ok.any() and np.sum(w) > 0 else float("nan")
