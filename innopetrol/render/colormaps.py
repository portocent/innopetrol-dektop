"""Color maps for fills colored by value."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtGui import QColor

from innopetrol.i18n import N_

# name -> (display name, translated with _() when shown; color stops from the left of the scale)
COLORMAPS = {
    "gamma_ray": (N_("Gamma ray (yellow → brown)"), ["#fff7bc", "#fee391", "#fec44f", "#ec7014", "#993404", "#4d2600"]),
    "resistivity": (N_("Resistivity (blue → red)"), ["#2166ac", "#67a9cf", "#d1e5f0", "#fddbc7", "#ef8a62", "#b2182b"]),
    "viridis": ("Viridis", ["#440154", "#3e4989", "#26828e", "#35b779", "#b5de2b", "#fde725"]),
    "rainbow": (N_("Rainbow"), ["#5e3c99", "#2b83ba", "#abdda4", "#ffffbf", "#fdae61", "#d7191c"]),
    "grayscale": (N_("Grayscale"), ["#f7f7f7", "#252525"]),
}
LEVELS = 48


@lru_cache(maxsize=None)
def palette(name: str, n: int = LEVELS) -> tuple[QColor, ...]:
    """n colors evenly spread over the color map (the first is the left of the scale)."""
    stops = [QColor(c) for c in COLORMAPS.get(name, COLORMAPS["viridis"])[1]]
    out = []
    for i in range(n):
        x = i / (n - 1) * (len(stops) - 1)
        j = min(int(x), len(stops) - 2)
        f = x - j
        a, b = stops[j], stops[j + 1]
        out.append(QColor(round(a.red() + (b.red() - a.red()) * f), round(a.green() + (b.green() - a.green()) * f),
                          round(a.blue() + (b.blue() - a.blue()) * f)))
    return tuple(out)
