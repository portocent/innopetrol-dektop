"""Petrophysics: Vsh, porosity, water saturation, net pay and zone summaries.

Every result is produced as a curve calculator *formula*, which documents how it was obtained
and lets it be recomputed when a project is reopened.

Parameters can change by zone (between formation tops): a zoned parameter is written into the
formula as `where((DEPTH >= top) & (DEPTH < base), value, …)`.

References:
- Larionov (1969): Vsh from the gamma-ray index.
- Archie (1942): Sw = (a·Rw / (φ^m·Rt))^(1/n).
- Simandoux (1963), modified total-shale form solved for n = 2:
  Sw = a·Rw/(2·φ^m) · [√((Vsh/Rsh)² + 4·φ^m/(a·Rw·Rt)) − Vsh/Rsh].
- Poupon & Leveaux (1971), "Indonesia":
  1/√Rt = [Vsh^(1 − Vsh/2)/√Rsh + √(φ^m/(a·Rw))] · Sw^(n/2).
- Arps (1953): Rw₂ = Rw₁ · (T₁ + k)/(T₂ + k), k = 21.5 °C or 6.77 °F.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from innopetrol.i18n import N_, _
from innopetrol.model import units
from innopetrol.model.calculator import curve_ref, evaluate
from innopetrol.model.tops import Zone, zones_from_tops
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
        sw = ((a * rw) / (phi**m * rt)) ** (1 / n)
    sw = np.where((phi > 0) & (rt > 0), sw, np.nan)
    return np.clip(sw, 0, 1)


def sw_simandoux(rt, phi, vsh, rw, rsh, a=1.0, m=2.0):
    rt, phi, vsh = (np.asarray(v, float) for v in (rt, phi, vsh))
    with np.errstate(all="ignore"):
        c = vsh / rsh
        sw = a * rw / (2 * phi**m) * (np.sqrt(c**2 + 4 * phi**m / (a * rw * rt)) - c)
    sw = np.where((phi > 0) & (rt > 0), sw, np.nan)
    return np.clip(sw, 0, 1)


def sw_indonesia(rt, phi, vsh, rw, rsh, a=1.0, m=2.0, n=2.0):
    rt, phi, vsh = (np.asarray(v, float) for v in (rt, phi, vsh))
    with np.errstate(all="ignore"):
        sw = ((1 / np.sqrt(rt)) / (vsh ** (1 - vsh / 2) / np.sqrt(rsh) + np.sqrt(phi**m / (a * rw)))) ** (2 / n)
    sw = np.where((phi > 0) & (rt > 0), sw, np.nan)
    return np.clip(sw, 0, 1)


ARPS_K = {"degC": 21.5, "degF": 6.77}


def rw_at_temperature(rw, t_rw, t, temp_unit="degC"):
    """Arps: resistivity of the water at temperature t, knowing rw at temperature t_rw."""
    k = ARPS_K[temp_unit]
    return rw * (t_rw + k) / (np.asarray(t, float) + k)


# ---------------------------------------------------------------- parameters and formulas

# Display names, translated with _() when shown.
VSH_METHODS = {
    "linear": N_("Linear (IGR)"),
    "larionov_tertiary": N_("Larionov (tertiary rocks)"),
    "larionov_older": N_("Larionov (older rocks)"),
}
PHI_METHODS = {
    "density": N_("Density"),
    "nd_average": N_("Neutron-density (average)"),
    "nd_rms": N_("Neutron-density (RMS, gas zones)"),
}
SW_MODELS = {
    "archie": N_("Archie (clean sands)"),
    "simandoux": N_("Simandoux (shaly sands, n = 2)"),
    "indonesia": N_("Indonesia (shaly sands, fresh water)"),
}
TEMP_MODES = {
    "none": N_("Rw is the same at every depth"),
    "gradient": N_("Geothermal gradient"),
    "curve": N_("Temperature curve"),
}
# Parameters that can be changed per zone, with their short labels.
ZONE_PARAMS = {
    "gr_clean": N_("Clean GR"),
    "gr_shale": N_("Shale GR"),
    "rho_ma": N_("ρ matrix"),
    "rho_fl": N_("ρ fluid"),
    "rw": "Rw",
    "a": "a",
    "m": "m",
    "n": "n",
    "rsh": "Rsh",
    "vsh_cut": "Vsh ≤",
    "phi_cut": "φe ≥",
    "sw_cut": "Sw ≤",
}


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
    sw_model: str = "archie"
    rsh: float = 2.0  # resistivity of the shale (ohm·m), used by the shaly-sand models
    # Rw at formation temperature (Arps). Temperatures in temp_unit; gradient in degrees per 100
    # depth units of the well (TVD).
    temp_mode: str = "none"
    temp_unit: str = "degC"
    rw_temp: float = 25.0  # temperature at which rw was measured
    surface_temp: float = 25.0
    gradient: float = 3.0
    temp_curve: str | None = None
    zones: dict[str, dict[str, float]] = field(default_factory=dict)  # zone name -> {parameter: value}

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> PetroParams:
        p = cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        p.zones = {
            str(z): {k: float(v) for k, v in vals.items() if k in ZONE_PARAMS} for z, vals in (p.zones or {}).items()
        }
        return p

    def value(self, key: str, zone: str | None = None) -> float:
        """A parameter in a zone: the zone's own value if it has one, otherwise the default."""
        return self.zones.get(zone, {}).get(key, getattr(self, key)) if zone else getattr(self, key)


@dataclass
class FormulaSpec:
    mnemonic: str
    unit: str
    description: str
    formula: str
    raw: str | None = None  # the same calculation before limiting to a valid range (for quality control)


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


def _num(v: float) -> str:
    return f"{v:.10g}"


def param_expr(well, p: PetroParams, key: str) -> str:
    """A parameter inside a formula: a number, or a piecewise expression of DEPTH if it changes by zone."""
    default = getattr(p, key)
    zones = zones_from_tops(well.tops, well.stop)
    expr = _num(default)
    for i, z in enumerate(zones):
        v = p.zones.get(z.name, {}).get(key)
        if v is None or v == default:
            continue
        # The last zone reaches the bottom of the log, including the last sample.
        cond = (
            f"(DEPTH >= {_num(z.top)})"
            if i == len(zones) - 1
            else f"(DEPTH >= {_num(z.top)}) & (DEPTH < {_num(z.base)})"
        )
        expr = f"where({cond}, {_num(v)}, {expr})"
    return expr


def _available(well, mnemonic: str | None, expected: str | None = None) -> str | None:
    """The mnemonic if the well has that curve (in a unit convertible to `expected`), otherwise None.

    A curve whose unit is of another kind cannot be used: old neutron logs, for example, are in API
    counts, not porosity, and must not be taken as a fraction.
    """
    from innopetrol.model.mnemonics import data_unit

    if not mnemonic or mnemonic not in well.curves:
        return None
    if expected is not None:
        unit = data_unit(well.curves[mnemonic], expected)
        if unit is not None and units.UNITS[unit].dimension != units.UNITS[expected].dimension:
            return None
    return mnemonic


class _Builder:
    """Builds the formulas of one calculation. Each step adds its curves; later steps refer to the
    earlier results by name (VSH, PHIE, SW…), so the order of the steps is the dependency order."""

    def __init__(self, well, p: PetroParams):
        self.well, self.p = well, p
        self.out: list[FormulaSpec] = []

    def param(self, key: str) -> str:
        return param_expr(self.well, self.p, key)

    def add(self, mnemonic: str, unit: str, description: str, formula: str, raw: str | None = None) -> None:
        self.out.append(FormulaSpec(mnemonic, unit, description, formula, raw))

    def has(self, mnemonic: str) -> bool:
        return any(f.mnemonic == mnemonic for f in self.out)

    def vsh(self) -> None:
        p = self.p
        gr = _available(self.well, p.gr_curve)
        if gr is None:
            return
        clean, shale = self.param("gr_clean"), self.param("gr_shale")
        igr = f"clip(({curve_ref(gr)} - {clean}) / ({shale} - {clean}), 0, 1)"
        vsh = {
            "linear": igr,
            "larionov_tertiary": f"clip(0.083 * (2 ** (3.7 * {igr}) - 1), 0, 1)",
            "larionov_older": f"clip(0.33 * (2 ** (2 * {igr}) - 1), 0, 1)",
        }[p.vsh_method]
        self.add("VSH", "v/v", _("Vsh - {method}").format(method=_(VSH_METHODS[p.vsh_method])), vsh)

    def porosity(self) -> None:
        p, well = self.p, self.well
        density, neutron = _available(well, p.rhob_curve, "g/cm3"), _available(well, p.nphi_curve, "v/v")
        if density is None:
            return
        rhob = input_ref(well, density, "g/cm3")
        rho_ma, rho_fl = self.param("rho_ma"), self.param("rho_fl")
        phid = f"({rho_ma} - {rhob}) / ({rho_ma} - {rho_fl})"
        method_key = p.phi_method if neutron is not None else "density"
        if method_key == "density" or neutron is None:
            method_key, phit = "density", phid
        else:
            phin = input_ref(well, neutron, "v/v")
            self.add("PHID", "v/v", _("Density porosity"), f"clip({phid}, -0.15, 0.6)")
            phit = f"(PHID + {phin}) / 2" if method_key == "nd_average" else f"sqrt((PHID ** 2 + {phin} ** 2) / 2)"
        method = _(PHI_METHODS[method_key])
        self.add("PHIT", "v/v", _("Total porosity - {method}").format(method=method), f"clip({phit}, 0, 0.6)", phit)
        phie = "clip(PHIT * (1 - VSH), 0, 0.6)" if self.has("VSH") else "PHIT"
        self.add("PHIE", "v/v", _("Effective porosity"), phie)

    def water_resistivity(self) -> str:
        """Rw inside the Sw formula: a parameter, or the RWT curve when corrected for temperature (Arps)."""
        p, well = self.p, self.well
        temperature = None
        if p.temp_mode == "gradient":
            self.add(
                "TFORM",
                p.temp_unit.upper(),
                _("Formation temperature from the geothermal gradient (TVD)"),
                f"{_num(p.surface_temp)} + {_num(p.gradient)} * TVD / 100",
            )
            temperature = "TFORM"
        elif p.temp_mode == "curve" and (curve := _available(well, p.temp_curve, p.temp_unit)) is not None:
            temperature = input_ref(well, curve, p.temp_unit)
        if not temperature:
            return self.param("rw")
        k = _num(ARPS_K[p.temp_unit])
        self.add(
            "RWT",
            "OHMM",
            _("Rw at formation temperature (Arps)"),
            f"{self.param('rw')} * ({_num(p.rw_temp)} + {k}) / ({temperature} + {k})",
        )
        return "RWT"

    def saturation(self) -> None:
        p = self.p
        resistivity = _available(self.well, p.rt_curve)
        if resistivity is None or not self.has("PHIE"):
            return
        rt = curve_ref(resistivity)
        rw = self.water_resistivity()
        a, m, n, rsh = self.param("a"), self.param("m"), self.param("n"), self.param("rsh")
        model = p.sw_model if self.has("VSH") and p.sw_model in SW_MODELS else "archie"
        if model == "simandoux":
            core = (
                f"({a} * {rw} / (2 * PHIE ** {m})) * "
                f"(sqrt((VSH / {rsh}) ** 2 + 4 * PHIE ** {m} / ({a} * {rw} * {rt})) - VSH / {rsh})"
            )
        elif model == "indonesia":
            core = (
                f"((1 / sqrt({rt})) / (VSH ** (1 - VSH / 2) / sqrt({rsh}) + sqrt(PHIE ** {m} / ({a} * {rw}))))"
                f" ** (2 / {n})"
            )
        else:
            core = f"(({a} * {rw}) / (PHIE ** {m} * {rt})) ** (1 / {n})"
        sw = f"where((PHIE > 0) & ({rt} > 0), clip({core}, 0, 1), nan)"
        raw = f"where((PHIE > 0) & ({rt} > 0), {core}, nan)"
        self.add("SW", "v/v", _("Sw - {model}").format(model=_(SW_MODELS[model])), sw, raw)

    def volumes(self) -> None:
        """For the lithology / fluids track: shale + matrix + porosity = 1, porosity split into water
        (BVW) and hydrocarbon (BVH)."""
        if self.has("PHIE") and self.has("VSH"):
            self.add("VMAT", "v/v", _("Matrix volume"), "clip(1 - VSH - PHIE, 0, 1)")
        if self.has("SW"):
            self.add("BVW", "v/v", _("Bulk volume water"), "PHIE * SW")
            self.add("BVH", "v/v", _("Bulk volume hydrocarbon"), "PHIE * (1 - SW)")

    def flags(self) -> None:
        if not self.has("PHIE"):
            return
        cond = f"(PHIE >= {self.param('phi_cut')})"
        if self.has("VSH"):
            cond = f"(VSH <= {self.param('vsh_cut')}) & {cond}"
        self.add("RES_FLAG", "", _("Net reservoir flag"), f"where(isnan(PHIE), nan, where({cond}, 1, 0))")
        if self.has("SW"):
            self.add(
                "PAY_FLAG",
                "",
                _("Net pay flag"),
                f"where(isnan(SW), nan, where((RES_FLAG > 0) & (SW <= {self.param('sw_cut')}), 1, 0))",
            )


def build_formulas(well, p: PetroParams) -> list[FormulaSpec]:
    """Formulas in dependency order, depending on which input curves are available."""
    b = _Builder(well, p)
    for step in (b.vsh, b.porosity, b.saturation, b.volumes, b.flags):
        step()
    return b.out


def compute(well, p: PetroParams) -> list[Curve]:
    """Evaluates the formulas; each result is available to the following ones."""
    env = well.formula_env()
    curves = []
    for spec in build_formulas(well, p):
        values = evaluate(spec.formula, env)
        env[spec.mnemonic] = values
        curves.append(Curve(spec.mnemonic, spec.unit, spec.description, values, formula=spec.formula))
    return curves


# ---------------------------------------------------------------- quality control

QC_MIN_SAMPLES = 5  # a finding needs at least this many samples…
QC_MIN_FRACTION = 0.02  # …and this fraction of the zone


@dataclass
class QcFinding:
    kind: str  # sw_above_1 | phi_negative | phi_high | density_range | neutron_range
    zone: str | None  # None = the whole well
    count: int
    fraction: float

    def message(self) -> str:
        pct = f"{self.fraction:.0%}"
        where = _(" in zone {zone}").format(zone=self.zone) if self.zone else ""
        texts = {
            "sw_above_1": _(
                "Sw above 1 in {pct} of the samples{where} before limiting: Rw or m may be too high, or the "
                "rock is shaly (try a shaly-sand model)."
            ),
            "phi_negative": _(
                "Porosity below 0 in {pct} of the samples{where}: the rock is denser than the matrix density "
                "(dolomite, anhydrite?) or the density is affected by the hole."
            ),
            "phi_high": _("Porosity above 0.6 in {pct} of the samples{where}: washed-out hole or wrong density units."),
            "density_range": _(
                "Density outside 1.0–3.2 g/cm³ in {pct} of the samples{where}: bad hole or wrong units."
            ),
            "neutron_range": _(
                "Neutron porosity above 0.6 in {pct} of the samples{where}: bad hole, or the curve is not porosity."
            ),
        }
        return texts[self.kind].format(pct=pct, where=where)


def qc_report(well, p: PetroParams, curves: list[Curve]) -> list[QcFinding]:
    """Results to review: values that had to be limited and inputs outside physical ranges, per zone."""
    env = well.formula_env()
    env.update({c.mnemonic: c.values for c in curves})
    checks: dict[str, np.ndarray] = {}
    raw = {spec.mnemonic: spec.raw for spec in build_formulas(well, p) if spec.raw}
    with np.errstate(invalid="ignore"):
        if "SW" in raw:
            checks["sw_above_1"] = evaluate(raw["SW"], env) > 1
        if "PHIT" in raw:
            phit = evaluate(raw["PHIT"], env)
            checks["phi_negative"], checks["phi_high"] = phit < 0, phit > 0.6
        density = _available(well, p.rhob_curve, "g/cm3")
        if density:
            rhob = evaluate(input_ref(well, density, "g/cm3"), env)
            checks["density_range"] = (rhob < 1.0) | (rhob > 3.2)
        neutron = _available(well, p.nphi_curve, "v/v")
        if neutron and "PHID" in env:
            checks["neutron_range"] = evaluate(input_ref(well, neutron, "v/v"), env) > 0.6
    # With tops, each zone is reported on its own (the part above the first top too); without, the whole well.
    zones: list[tuple[str | None, np.ndarray]] = [(None, np.ones(well.depth.shape, bool))]
    if well.tops:
        first = min(t.depth for t in well.tops)
        zones = [(_("(above the first top)"), well.interval_mask(None, first))] if first > well.start else []
        zones += [(z.name, well.interval_mask(z.top, z.base)) for z in zones_from_tops(well.tops, well.stop)]
    findings = []
    for kind, flagged in checks.items():
        for name, mask in zones:
            count, total = int(np.sum(flagged & mask)), int(np.sum(mask))
            if total and count >= QC_MIN_SAMPLES and count / total >= QC_MIN_FRACTION:
                findings.append(QcFinding(kind, name, count, count / total))
    return findings


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


def zone_summary(
    well,
    zones: list[Zone],
    vsh: str | None,
    phi: str | None,
    sw: str | None,
    vsh_cut: float,
    phi_cut: float,
    sw_cut: float,
    zone_cutoffs: dict[str, dict[str, float]] | None = None,
) -> list[ZoneSummary]:
    """Gross, net reservoir and net pay thickness, N/G and averages per zone.

    Averages: φ weighted by thickness over net reservoir; Sw weighted by φ·h over net pay.
    `zone_cutoffs` (zone name -> {"vsh_cut": …}) replaces the cutoffs in the zones that define them.
    """
    h = sample_thickness(well.depth)
    nan = np.full(well.depth.shape, np.nan)
    v = _as_fraction(well, vsh, nan)
    f = _as_fraction(well, phi, nan)
    s = _as_fraction(well, sw, nan)

    out = []
    for z in zones:
        own = (zone_cutoffs or {}).get(z.name, {})
        res = np.isfinite(f) & (f >= own.get("phi_cut", phi_cut))
        if vsh in well.curves:
            res &= np.isfinite(v) & (v <= own.get("vsh_cut", vsh_cut))
        pay = res & np.isfinite(s) & (s <= own.get("sw_cut", sw_cut))
        m = well.interval_mask(z.top, z.base)
        gross = float(h[m].sum())
        net_r = float(h[m & res].sum())
        net_p = float(h[m & pay].sum())
        out.append(
            ZoneSummary(
                zone=z.name,
                top=z.top,
                base=z.base,
                gross=gross,
                net_reservoir=net_r,
                net_pay=net_p,
                ntg=net_r / gross if gross else float("nan"),
                phi_avg=_wavg(f, h, m & res),
                sw_avg=_wavg(s, h * np.nan_to_num(f), m & pay),
                vsh_avg=_wavg(v, h, m & res),
            )
        )
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
