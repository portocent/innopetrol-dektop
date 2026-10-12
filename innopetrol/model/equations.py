"""The equations InnoPetrol uses, with their variables, validity and bibliographic references.

Shown to the user (Help ▸ Equations and references, and the "?" buttons of the petrophysics
dialog) so every result can be traced to its source. Keys are the method keys of model.petro
(VSH_METHODS, PHI_METHODS, SW_MODELS) plus the temperature correction and the survey method.
Formulas are HTML with Unicode symbols; names, variables and notes are marked for translation.
"""

from __future__ import annotations

from dataclasses import dataclass

from innopetrol.i18n import N_


@dataclass(frozen=True)
class Equation:
    key: str
    name: str  # translated with _() when shown
    formula: str  # HTML
    variables: tuple[tuple[str, str], ...]  # (symbol, description translated with _())
    note: str  # validity / how InnoPetrol applies it; translated with _()
    reference: str  # bibliographic reference (not translated)


_V_IGR = (
    "I<sub>GR</sub>",
    N_("gamma-ray index = (GR − GR<sub>clean</sub>) / (GR<sub>shale</sub> − GR<sub>clean</sub>), limited to 0–1"),
)
_V_VSH = ("V<sub>sh</sub>", N_("shale volume (fraction)"))
_V_PHI = ("φ", N_("effective porosity (fraction)"))
_V_RT = ("R<sub>t</sub>", N_("true formation resistivity (ohm·m), the deep resistivity curve"))
_V_RW = ("R<sub>w</sub>", N_("formation water resistivity at formation temperature (ohm·m)"))
_V_RSH = ("R<sub>sh</sub>", N_("resistivity of the shale (ohm·m)"))
_V_AMN = ("a, m, n", N_("tortuosity factor, cementation exponent and saturation exponent"))

_ASQUITH = "Asquith, G., Krygowski, D. (2004). Basic Well Log Analysis, 2nd ed. AAPG Methods in Exploration 16."

EQUATIONS: dict[str, Equation] = {
    e.key: e
    for e in (
        Equation(
            "linear",
            N_("Shale volume, linear"),
            "V<sub>sh</sub> = I<sub>GR</sub>",
            (_V_IGR,),
            N_("Usually overestimates the shale volume; Larionov's corrections are often preferred."),
            _ASQUITH,
        ),
        Equation(
            "larionov_tertiary",
            N_("Shale volume, Larionov (tertiary rocks)"),
            "V<sub>sh</sub> = 0.083 · (2<sup>3.7·I<sub>GR</sub></sup> − 1)",
            (_V_IGR,),
            N_("For young, unconsolidated rocks."),
            "Larionov, V. V. (1969). Borehole Radiometry. Nedra, Moscow.",
        ),
        Equation(
            "larionov_older",
            N_("Shale volume, Larionov (older rocks)"),
            "V<sub>sh</sub> = 0.33 · (2<sup>2·I<sub>GR</sub></sup> − 1)",
            (_V_IGR,),
            N_("For older, consolidated rocks."),
            "Larionov, V. V. (1969). Borehole Radiometry. Nedra, Moscow.",
        ),
        Equation(
            "density",
            N_("Density porosity"),
            "φ<sub>D</sub> = (ρ<sub>ma</sub> − ρ<sub>b</sub>) / (ρ<sub>ma</sub> − ρ<sub>fl</sub>)",
            (
                ("ρ<sub>b</sub>", N_("bulk density from the log (g/cm³)")),
                ("ρ<sub>ma</sub>, ρ<sub>fl</sub>", N_("matrix and fluid density (g/cm³)")),
            ),
            N_(
                "Total porosity limited to 0–0.6. "
                "Effective porosity: φ<sub>e</sub> = φ<sub>T</sub>·(1 − V<sub>sh</sub>)."
            ),
            _ASQUITH,
        ),
        Equation(
            "nd_average",
            N_("Neutron-density porosity (average)"),
            "φ<sub>T</sub> = (φ<sub>D</sub> + φ<sub>N</sub>) / 2",
            (("φ<sub>D</sub>, φ<sub>N</sub>", N_("density and neutron porosity (fraction)")),),
            N_("φ<sub>D</sub> limited to −0.15–0.6 and φ<sub>T</sub> to 0–0.6; neutron in the matrix of the density."),
            _ASQUITH,
        ),
        Equation(
            "nd_rms",
            N_("Neutron-density porosity (RMS, gas zones)"),
            "φ<sub>T</sub> = √((φ<sub>D</sub>² + φ<sub>N</sub>²) / 2)",
            (("φ<sub>D</sub>, φ<sub>N</sub>", N_("density and neutron porosity (fraction)")),),
            N_("Corrects for the effect of gas, which lowers the neutron and raises the density porosity."),
            "Gaymard, R., Poupon, A. (1968). Response of neutron and formation density logs in hydrocarbon "
            "bearing formations. The Log Analyst 9(5).",
        ),
        Equation(
            "archie",
            N_("Water saturation, Archie"),
            "S<sub>w</sub> = ( a·R<sub>w</sub> / (φ<sup>m</sup>·R<sub>t</sub>) )<sup>1/n</sup>",
            (_V_PHI, _V_RT, _V_RW, _V_AMN),
            N_("Valid in clean (shale-free) rock. Limited to 0–1."),
            "Archie, G. E. (1942). The electrical resistivity log as an aid in determining some reservoir "
            "characteristics. Trans. AIME 146, 54–62.",
        ),
        Equation(
            "simandoux",
            N_("Water saturation, Simandoux"),
            "S<sub>w</sub> = (a·R<sub>w</sub> / 2φ<sup>m</sup>) · [ √((V<sub>sh</sub>/R<sub>sh</sub>)² + "
            "4φ<sup>m</sup> / (a·R<sub>w</sub>·R<sub>t</sub>)) − V<sub>sh</sub>/R<sub>sh</sub> ]",
            (_V_PHI, _V_VSH, _V_RT, _V_RW, _V_RSH, _V_AMN),
            N_(
                "Shaly sands. Total-shale form solved for n = 2 (the n entered is not used). "
                "Equals Archie when V<sub>sh</sub> = 0."
            ),
            "Simandoux, P. (1963). Dielectric measurements on porous media: application to the measurement of "
            "water saturations. Revue de l'Institut Français du Pétrole 18, 193–215.",
        ),
        Equation(
            "indonesia",
            N_("Water saturation, Indonesia"),
            "1/√R<sub>t</sub> = [ V<sub>sh</sub><sup>(1 − V<sub>sh</sub>/2)</sup>/√R<sub>sh</sub> + "
            "√(φ<sup>m</sup> / (a·R<sub>w</sub>)) ] · S<sub>w</sub><sup>n/2</sup>",
            (_V_PHI, _V_VSH, _V_RT, _V_RW, _V_RSH, _V_AMN),
            N_("Shaly sands with fresh formation water. Equals Archie when V<sub>sh</sub> = 0."),
            "Poupon, A., Leveaux, J. (1971). Evaluation of water saturation in shaly formations. "
            "SPWLA 12th Annual Logging Symposium.",
        ),
        Equation(
            "arps",
            N_("Rw at formation temperature, Arps"),
            "R<sub>w2</sub> = R<sub>w1</sub> · (T<sub>1</sub> + k) / (T<sub>2</sub> + k)",
            (
                ("R<sub>w1</sub>, T<sub>1</sub>", N_("water resistivity and the temperature it was measured at")),
                ("T<sub>2</sub>", N_("formation temperature")),
                ("k", N_("21.5 for °C, 6.77 for °F")),
            ),
            N_("NaCl solutions; the usual correction in log analysis."),
            "Arps, J. J. (1953). The effect of temperature on the density and electrical resistivity of sodium "
            "chloride solutions. Trans. AIME 198, 327–330.",
        ),
        Equation(
            "geothermal",
            N_("Formation temperature from a geothermal gradient"),
            "T = T<sub>surface</sub> + G · TVD / 100",
            (("G", N_("geothermal gradient, degrees per 100 depth units")), ("TVD", N_("true vertical depth"))),
            N_("TVD is measured from the depth reference of the well (KB/DF), not from the ground."),
            _ASQUITH,
        ),
        Equation(
            "minimum_curvature",
            N_("Wellbore trajectory, minimum curvature"),
            "ΔTVD = (ΔMD/2)·(cos I<sub>1</sub> + cos I<sub>2</sub>)·RF,  RF = (2/β)·tan(β/2)",
            (
                ("I<sub>1</sub>, I<sub>2</sub>", N_("inclination at two survey stations")),
                ("β", N_("dogleg angle between the stations")),
            ),
            N_(
                "The hole between stations is a circular arc; log samples between stations are placed on the "
                "arc (north and east are computed the same way)."
            ),
            "Taylor, H. L., Mason, M. C. (1972). A systematic approach to well surveying calculations. "
            "SPE Journal 12(6), 474–488.",
        ),
    )
}

# Equations behind each temperature mode of the petrophysics.
TEMPERATURE_EQUATIONS = {"none": (), "gradient": ("geothermal", "arps"), "curve": ("arps",)}

# Sections of the "Equations and references" window, in order (title translated with _()).
SECTIONS = (
    (N_("Shale volume"), ("linear", "larionov_tertiary", "larionov_older")),
    (N_("Porosity"), ("density", "nd_average", "nd_rms")),
    (N_("Water saturation"), ("archie", "simandoux", "indonesia")),
    (N_("Water resistivity and temperature"), ("arps", "geothermal")),
    (N_("Depth"), ("minimum_curvature",)),
)


def curve_equations(mnemonic: str, params, has_vsh: bool) -> tuple[str, ...]:
    """Equations behind a curve computed by the petrophysics (empty for other curves).

    `params` are the PetroParams the curves were computed with; `has_vsh` tells whether shale volume
    was available (without it, saturation falls back to Archie).
    """
    if params is None:
        return ()
    by_curve = {
        "VSH": (params.vsh_method,),
        "PHID": ("density",),
        "PHIT": ("density",) if params.phi_method == "density" else ("density", params.phi_method),
        "PHIE": ("density",),
        "SW": (params.sw_model if has_vsh else "archie",),
        "RWT": ("arps",),
        "TFORM": ("geothermal",),
    }
    return tuple(k for k in by_curve.get(mnemonic, ()) if k in EQUATIONS)
