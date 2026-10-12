"""Normalization of a curve across wells (typically gamma ray before computing Vsh in several wells).

Two-point normalization: in each well, the low and high percentiles of the curve within a zone are
mapped to target values (those of a reference well, or typed), so the same rock reads the same in
every well despite different tools, calibrations or hole conditions:

    CURVE_N = T_low + (CURVE − P_low) · (T_high − T_low) / (P_high − P_low)

The result is a formula, so it records the percentiles used and is recomputed with the project.
"""

from __future__ import annotations

import numpy as np

from innopetrol.model.calculator import curve_ref
from innopetrol.model.tops import zones_from_tops


def zone_mask(well, zone: str | None) -> np.ndarray:
    """Samples inside the zone of that name, using the well's own tops (None = the whole well)."""
    if zone is None:
        return np.ones(well.depth.shape, bool)
    mask = np.zeros(well.depth.shape, bool)
    for z in zones_from_tops(well.tops, well.stop):
        if z.name == zone:
            mask |= well.interval_mask(z.top, z.base)
    return mask


def percentiles(values: np.ndarray, mask: np.ndarray, low: float, high: float) -> tuple[float, float] | None:
    """(P_low, P_high) of the values inside the mask, or None if there are too few samples."""
    v = np.asarray(values, float)[mask]
    v = v[np.isfinite(v)]
    if v.size < 10:
        return None
    lo, hi = np.percentile(v, [low, high])
    return (float(lo), float(hi)) if hi > lo else None


def normalization_formula(mnemonic: str, points: tuple[float, float], targets: tuple[float, float]) -> str:
    """Formula mapping the well's percentile points to the target values (linear, two points)."""
    (lo, hi), (t_lo, t_hi) = points, targets
    return f"{t_lo:.10g} + ({curve_ref(mnemonic)} - {lo:.10g}) * ({t_hi - t_lo:.10g}) / ({hi - lo:.10g})"
