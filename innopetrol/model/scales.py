"""Conversión valor→píxel (lineal/log), escalas por defecto y marcas de profundidad.

Todo está vectorizado con numpy: se transforma la curva completa de una sola vez en lugar
de recorrer muestra por muestra en Python.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

MM_PER_UNIT = {"m": 1000.0, "ft": 304.8}
SCALE_PRESETS = [10, 20, 25, 50, 100, 200, 240, 500, 1000, 2000, 5000]


def map_values(values: np.ndarray, left: float, right: float, log: bool, width: float) -> np.ndarray:
    """Mapea valores a coordenada x en [0, width]. Permite escalas invertidas (left > right).

    En escala log los valores <= 0 no existen y quedan como NaN.
    """
    values = np.asarray(values, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        if log:
            if left <= 0 or right <= 0:
                return np.full(values.shape, np.nan)
            v = np.where(values > 0, values, np.nan)
            lo, hi = math.log10(left), math.log10(right)
            t = (np.log10(v) - lo) / (hi - lo)
        else:
            if right == left:
                return np.full(values.shape, np.nan)
            t = (values - left) / (right - left)
    return t * width


def map_value(value: float, left: float, right: float, log: bool, width: float) -> float:
    return float(map_values(np.array([value]), left, right, log, width)[0])


def nice_linear_range(vmin: float, vmax: float) -> tuple[float, float]:
    """Rango 'redondo' que contiene los datos (p. ej. 13.9–139.7 → 0–150)."""
    if not (math.isfinite(vmin) and math.isfinite(vmax)):
        return 0.0, 1.0
    if vmin == vmax:
        return vmin - 1, vmax + 1
    span = vmax - vmin
    base = 10 ** (math.floor(math.log10(span)) - 1)
    step = base * 10
    for mult in (1, 2, 2.5, 5, 10, 20, 25, 50, 100):
        if span / (base * mult) <= 6:
            step = base * mult
            break
    lo = math.floor(vmin / step) * step
    hi = math.ceil(vmax / step) * step
    if vmin >= 0 and lo < 0:
        lo = 0.0
    return _clean(lo), _clean(hi)


def log_decades(vmin: float, vmax: float) -> tuple[float, float]:
    """Década completa que contiene los datos positivos (p. ej. 0.47–72 → 0.1–100)."""
    if not math.isfinite(vmax) or vmax <= 0:
        return 0.1, 1000.0
    if not math.isfinite(vmin) or vmin <= 0:
        vmin = vmax / 1000
    lo = 10 ** math.floor(math.log10(vmin))
    hi = 10 ** math.ceil(math.log10(vmax))
    if hi <= lo:
        hi = lo * 10
    return _clean(lo), _clean(hi)


def log_grid_positions(left: float, right: float) -> list[tuple[float, bool]]:
    """Valores de las líneas de grilla log: (valor, es_década)."""
    lo, hi = sorted((left, right))
    if lo <= 0:
        return []
    out = []
    for k in range(math.floor(math.log10(lo)), math.ceil(math.log10(hi)) + 1):
        base = 10.0 ** k
        for m in range(1, 10):
            v = m * base
            if lo * (1 - 1e-9) <= v <= hi * (1 + 1e-9):
                out.append((v, m == 1))
    return out


def px_per_unit(scale_ratio: float, dpi: float, depth_unit: str) -> float:
    """Píxeles por unidad de profundidad para una escala 1:N real en pantalla/papel.

    Ej.: escala 1:500 en metros → 1 m = 2 mm de papel → 2 mm * dpi/25.4 píxeles.
    """
    return dpi / 25.4 * MM_PER_UNIT.get(depth_unit, 1000.0) / scale_ratio


def scale_ratio(ppu: float, dpi: float, depth_unit: str) -> float:
    return dpi / 25.4 * MM_PER_UNIT.get(depth_unit, 1000.0) / ppu


@dataclass
class DepthTicks:
    minor: np.ndarray
    major: np.ndarray
    labels: np.ndarray
    label_interval: float


_INTERVALS = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000]


def depth_ticks(top: float, bottom: float, ppu: float, min_px: float = 6, label_px: float = 40) -> DepthTicks:
    """Marcas de profundidad sin acumular errores de punto flotante.

    El código original sumaba `i += step` y preguntaba `i % 1000 == 0`; con pasos de 0.5 o 0.1
    el redondeo hacía que algunas marcas nunca aparecieran. Aquí se generan como múltiplos
    enteros del intervalo, elegidos según cuántos píxeles separan cada marca.
    """
    minor_iv = next((iv for iv in _INTERVALS if iv * ppu >= min_px), _INTERVALS[-1])
    major_iv = next((iv for iv in _INTERVALS if iv >= minor_iv * 5 and iv * ppu >= min_px * 4), minor_iv * 5)
    label_iv = next((iv for iv in _INTERVALS if iv >= minor_iv and iv * ppu >= label_px), _INTERVALS[-1])

    def multiples(iv):
        k0, k1 = math.ceil(top / iv), math.floor(bottom / iv)
        return np.arange(k0, k1 + 1) * iv

    return DepthTicks(multiples(minor_iv), multiples(major_iv), multiples(label_iv), label_iv)


def _clean(v: float) -> float:
    return float(f"{v:.10g}")
