"""Read-only view of a well in a display depth reference (MD / TVD / TVDSS) and unit.

Drawing code works with "a well" (depth array, curves, tops, labels). This adapter gives it the
depths it should draw against, without changing the stored data: curves, tops and calculations
always stay in measured depth (MD) in the file's unit.
"""

from __future__ import annotations

import numpy as np

from innopetrol.i18n import _
from innopetrol.model import units
from innopetrol.model.scales import MM_PER_UNIT
from innopetrol.model.tops import Top

REFERENCES = ("md", "tvd", "tvdss")


class DepthView:
    def __init__(self, well, reference: str = "md", unit: str | None = None,
                 curve_units: dict[str, str] | None = None):
        self.well = well
        self.curve_units = dict(curve_units or {})  # mnemonic -> display unit (canonical key)
        self._curves = None
        if reference == "tvdss" and well.elevation is None:
            reference = "tvd"
        self.reference = reference if reference in REFERENCES else "md"
        self.depth_unit = unit if unit in MM_PER_UNIT else well.depth_unit
        self._factor = MM_PER_UNIT[well.depth_unit] / MM_PER_UNIT[self.depth_unit]
        axis = well.depth if self.reference == "md" else well.tvd()
        if self.reference == "tvdss":
            axis = axis - well.elevation
        # Drawing needs a non-decreasing axis; TVD only decreases in wells drilled upwards, which are
        # then drawn flat over that section.
        self.depth = np.maximum.accumulate(axis * self._factor)

    # ----------------------------------------------------------------- delegated well data
    def __getattr__(self, name):
        return getattr(self.well, name)  # curves, header, name, notes, header_value, path…

    @property
    def curves(self) -> dict:
        """Curves with values in their display unit (stored data is never modified)."""
        if self._curves is None:
            from innopetrol.model.well import Curve

            self._curves = {}
            for mnem, c in self.well.curves.items():
                target = self.curve_units.get(mnem)
                if target:
                    try:
                        values = units.convert(c.values, display_source_unit(c, target), target)
                    except ValueError:
                        target, values = None, c.values
                if target:
                    self._curves[mnem] = Curve(mnem, units.label(target), c.description, values, c.formula)
                else:
                    self._curves[mnem] = c
        return self._curves

    def display_value(self, mnemonic: str, value: float) -> float:
        target = self.curve_units.get(mnemonic)
        if not target or mnemonic not in self.well.curves:
            return value
        c = self.well.curves[mnemonic]
        return float(units.convert(value, display_source_unit(c, target), target))

    @property
    def depth_mnemonic(self) -> str:
        return self.well.depth_mnemonic if self.reference == "md" else self.reference.upper()

    @property
    def start(self) -> float:
        return float(self.depth[0])

    @property
    def stop(self) -> float:
        return float(self.depth[-1])

    @property
    def tops(self) -> list[Top]:
        return [Top(t.name, float(self.to_display(t.depth)), t.color) for t in self.well.tops]

    @property
    def description(self) -> str:
        names = {"md": _("measured depth (MD)"), "tvd": _("true vertical depth (TVD)"),
                 "tvdss": _("true vertical depth subsea (TVDSS)")}
        return names[self.reference]

    # ----------------------------------------------------------------- conversions
    def to_display(self, md):
        """Display depth for measured depths (in the file unit)."""
        md = np.asarray(md, dtype=float)
        if self.reference == "md":
            return md * self._factor
        result = np.interp(md, self.well.depth, self.depth)
        return result

    def to_md(self, display):
        """Measured depth (file unit) for display depths."""
        display = np.asarray(display, dtype=float)
        if self.reference == "md":
            return display / self._factor
        return np.interp(display, self.depth, self.well.depth)

    def value_at(self, mnemonic: str, display_depth: float) -> float:
        return self.display_value(mnemonic, self.well.value_at(mnemonic, float(self.to_md(display_depth))))


def display_source_unit(curve, target: str) -> str | None:
    """Unit of a curve's stored values, checked against its values (mislabeled % / kg/m³)."""
    from innopetrol.model.mnemonics import data_unit

    dim = units.UNITS[target].dimension
    expected = {"fraction": "v/v", "density": "g/cm3"}.get(dim)
    return data_unit(curve, expected) if expected else units.normalize(curve.unit)
