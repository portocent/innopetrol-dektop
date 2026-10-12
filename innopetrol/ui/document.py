"""WellDocument: an open well plus its layout, with signals so views can update themselves."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from innopetrol.model import units
from innopetrol.model.depth_view import DepthView, display_source_unit
from innopetrol.model.layout import LogLayout, TrackSpec
from innopetrol.model.petro import PetroParams
from innopetrol.model.well import Curve, Well


class WellDocument(QObject):
    layoutChanged = Signal()
    curvesChanged = Signal()
    topsChanged = Signal()
    cursorMoved = Signal(float)  # measured depth (MD, file unit) under the cursor; NaN = outside

    def __init__(self, well: Well, layout: LogLayout, petro: PetroParams | None = None, parent=None):
        super().__init__(parent)
        self.well = well
        self.layout = layout
        self.petro = petro
        self.depth_reference = "md"  # "md" | "tvd" | "tvdss": axis used to draw the well
        self.display_unit: str | None = None  # None = the file's depth unit
        self.curve_units: dict[str, str] = {}  # mnemonic -> display unit; missing = file unit
        self._view: DepthView | None = None

    @property
    def title(self) -> str:
        return self.well.name

    @property
    def view(self) -> DepthView:
        """The well as it is drawn: depths in the chosen reference and unit. Data stays in MD."""
        if self._view is None:
            self._view = DepthView(self.well, self.depth_reference, self.display_unit, self.curve_units)
        return self._view

    def set_depth_display(self, reference: str | None = None, unit: str | None | bool = False) -> None:
        """Changes the drawing reference (MD/TVD/TVDSS) and/or unit (None = file unit)."""
        if reference is not None:
            self.depth_reference = reference
        if unit is not False:
            self.display_unit = unit
        self._view = None
        self.layoutChanged.emit()

    # ----------------------------------------------------------------- curve display units
    def display_unit_of(self, mnemonic: str) -> str | None:
        """Unit a curve is displayed in (canonical key), or its file unit text if not converted."""
        if mnemonic in self.curve_units:
            return self.curve_units[mnemonic]
        curve = self.well.curves.get(mnemonic)
        return curve.unit if curve else None

    def _convert_scales(self, mnemonic: str, old: str | None, new: str | None) -> None:
        """Rewrites track scales and fixed fill values of a curve from one unit to another."""
        def conv(v):
            if v is None:
                return None
            try:
                return float(f"{float(units.convert(v, old, new)):.6g}")
            except ValueError:
                return v

        for track in self.layout.tracks:
            for c in track.curves:
                if c.mnemonic == mnemonic:
                    c.left, c.right, c.unit = conv(c.left), conv(c.right), new
            for f in track.fills:
                if f.left_value is not None and f.right_curve == mnemonic:
                    f.left_value = conv(f.left_value)
                if f.right_value is not None and f.left_curve == mnemonic:
                    f.right_value = conv(f.right_value)

    def set_curve_unit(self, mnemonic: str, unit: str | None, notify: bool = True) -> None:
        """Displays a curve in another unit (None = back to the file unit)."""
        curve = self.well.curves.get(mnemonic)
        current = self.curve_units.get(mnemonic)
        if curve is None or (unit is None and current is None):
            return
        source = display_source_unit(curve, unit or current)  # unit of the stored values
        old = current or source or curve.unit
        new = unit or source or curve.unit
        if old != new:
            self._convert_scales(mnemonic, old, new)
        if unit and unit != source:
            self.curve_units[mnemonic] = unit
        else:
            self.curve_units.pop(mnemonic, None)
        self._view = None
        if notify:
            self.layoutChanged.emit()

    def apply_unit_system(self, system: str) -> None:
        """Displays every curve (and depth) with the preferred units of a unit system."""
        for mnem, curve in self.well.curves.items():
            target = units.system_unit(curve.unit, system)
            if target is None and system != "file" and mnem not in self.curve_units:
                continue
            self.set_curve_unit(mnem, target, notify=False)
        self.display_unit = units.SYSTEM_DEPTH_UNIT.get(system)
        self._view = None
        self.layoutChanged.emit()

    def adopt_layout(self, layout: LogLayout) -> LogLayout:
        """Converts a layout's scales (written in each style's unit) to this well's display units."""
        for track in layout.tracks:
            for c in track.curves:
                target = self.display_unit_of(c.mnemonic)
                if c.unit and target and units.normalize(c.unit) != units.normalize(target):
                    try:
                        c.left, c.right = (None if v is None else float(f"{float(units.convert(v, c.unit, target)):.6g}")
                                           for v in (c.left, c.right))
                    except ValueError:
                        pass
                c.unit = target
        return layout

    def style_for(self, mnemonic: str):
        """Default style for a curve, with its scale in the curve's display unit."""
        from innopetrol.model.layout import LogLayout as _Layout, TrackSpec as _Track
        from innopetrol.model.mnemonics import make_curve_style

        style = make_curve_style(self.well, mnemonic)
        self.adopt_layout(_Layout([_Track(curves=[style])]))
        return style

    def set_survey(self, survey, elevation: float | None) -> None:
        self.well.survey = survey
        self.well.elevation = elevation
        self._view = None
        if self.depth_reference == "tvdss" and elevation is None:
            self.depth_reference = "tvd"
        self.layoutChanged.emit()

    def set_layout(self, layout: LogLayout) -> None:
        self.layout = layout
        self.layoutChanged.emit()

    def set_track(self, index: int, track: TrackSpec) -> None:
        self.layout.tracks[index] = track
        self.layoutChanged.emit()

    def insert_track(self, index: int, track: TrackSpec) -> None:
        self.layout.tracks.insert(index, track)
        self.layoutChanged.emit()

    def remove_track(self, index: int) -> None:
        if 0 <= index < len(self.layout.tracks):
            del self.layout.tracks[index]
            self.layoutChanged.emit()

    def move_track(self, index: int, delta: int) -> int:
        j = index + delta
        if 0 <= index < len(self.layout.tracks) and 0 <= j < len(self.layout.tracks):
            t = self.layout.tracks
            t[index], t[j] = t[j], t[index]
            self.layoutChanged.emit()
            return j
        return index

    def add_curves(self, curves: list[Curve]) -> None:
        for c in curves:
            self.well.add_curve(c)
        self.curvesChanged.emit()
        self.layoutChanged.emit()

    def remove_curve(self, mnemonic: str) -> None:
        self.well.remove_curve(mnemonic)
        for t in self.layout.tracks:
            t.curves = [c for c in t.curves if c.mnemonic != mnemonic]
            t.fills = [f for f in t.fills if mnemonic not in (f.left_curve, f.right_curve)]
        self.curvesChanged.emit()
        self.layoutChanged.emit()

    def set_tops(self, tops) -> None:
        self.well.tops = sorted(tops, key=lambda t: t.depth)
        self.topsChanged.emit()
        self.layoutChanged.emit()
