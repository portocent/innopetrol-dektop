"""WellDocument: an open well plus its layout, with signals so views can update themselves.

Undo/redo works with snapshots: every change to the well's *content* (layout, tops, curves,
petrophysics parameters, survey) is detected by comparing the state after each change signal with
the previous one, and pushed to a QUndoStack. Views of the data (depth reference, display units)
are not content and are not undone; layouts restored by an undo are converted to the current
display units through `adopt_layout`.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QUndoCommand, QUndoStack

from innopetrol.i18n import _
from innopetrol.model import units
from innopetrol.model.depth_view import DepthView, display_source_unit
from innopetrol.model.intervals import Interval
from innopetrol.model.layout import LogLayout, TrackSpec
from innopetrol.model.location import Location
from innopetrol.model.petro import PetroParams
from innopetrol.model.survey import Survey
from innopetrol.model.tops import Top
from innopetrol.model.well import Curve, Well


@dataclass
class _State:
    """Content of a well that can be undone. Curves are shared, never copied: curve objects are not
    modified once created, so keeping references is enough and costs no memory."""

    layout: dict
    tops: list
    curves: dict
    petro: dict | None
    survey: Survey | None
    elevation: float | None
    location: Location | None = None
    intervals: list = field(default_factory=list)  # as dicts

    def same_as(self, other: _State) -> bool:
        return (
            self.layout == other.layout
            and self.tops == other.tops
            and self.petro == other.petro
            and self.survey is other.survey
            and self.elevation == other.elevation
            and self.location == other.location
            and self.intervals == other.intervals
            and list(self.curves) == list(other.curves)
            and all(c is other.curves[m] for m, c in self.curves.items())
        )


class _SnapshotCommand(QUndoCommand):
    def __init__(self, doc: WellDocument, before: _State, after: _State, text: str):
        super().__init__(text)
        self.doc, self.before, self.after = doc, before, after
        self._done = True  # the change already happened when the command is pushed

    def redo(self):
        if self._done:
            self._done = False
            return
        self.doc._restore(self.after)

    def undo(self):
        self.doc._restore(self.before)


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
        self.undo_stack = QUndoStack(self)
        self._baseline = self._state()
        self._step_depth = 0
        self._step_text: str | None = None
        self._restoring = False
        for signal in (self.layoutChanged, self.curvesChanged, self.topsChanged):
            signal.connect(self._record)

    # ----------------------------------------------------------------- undo / redo
    def _state(self) -> _State:
        return _State(
            self.layout.to_dict(),
            [t.to_dict() for t in self.well.tops],
            dict(self.well.curves),
            self.petro.to_dict() if self.petro else None,
            self.well.survey,
            self.well.elevation,
            self.well.location,
            [i.to_dict() for i in self.well.intervals],
        )

    def _record(self) -> None:
        """Pushes an undo step if the content changed since the last recorded state."""
        if self._restoring or self._step_depth:
            return
        state = self._state()
        if not state.same_as(self._baseline):
            before, self._baseline = self._baseline, state
            self.undo_stack.push(_SnapshotCommand(self, before, state, self._step_text or _("Edit")))
        self._step_text = None

    def reset_history(self) -> None:
        """Forgets the undo history and takes the current content as the starting point."""
        self.undo_stack.clear()
        self._baseline = self._state()

    @contextmanager
    def undo_step(self, text: str):
        """Groups every change made inside the block into one undo step called `text`."""
        if self._step_depth == 0:
            self._step_text = text
        self._step_depth += 1
        try:
            yield
        finally:
            self._step_depth -= 1
            if self._step_depth == 0:
                self._record()

    @contextmanager
    def _untracked(self):
        """Changes to how the data is displayed (units): not undoable, they become the new baseline."""
        self._step_depth += 1
        try:
            yield
        finally:
            self._step_depth -= 1
            if self._step_depth == 0:
                self._baseline = self._state()

    def _restore(self, state: _State) -> None:
        self._restoring = True
        try:
            self.well.curves = dict(state.curves)
            self.well.tops = [Top.from_dict(t) for t in state.tops]
            self.petro = PetroParams.from_dict(state.petro) if state.petro else None
            self.well.survey, self.well.elevation = state.survey, state.elevation
            self.well.location = state.location
            self.well.intervals = [Interval.from_dict(i) for i in state.intervals]
            if self.depth_reference == "tvdss" and self.well.elevation is None:
                self.depth_reference = "tvd"
            for mnem in [m for m in self.curve_units if m not in self.well.curves]:
                del self.curve_units[mnem]
            self.layout = self.adopt_layout(LogLayout.from_dict(state.layout))
            self._view = None
            self.curvesChanged.emit()
            self.topsChanged.emit()
            self.layoutChanged.emit()
        finally:
            self._restoring = False
        self._baseline = self._state()

    @property
    def title(self) -> str:
        return self.well.name

    @property
    def view(self) -> DepthView:
        """The well as it is drawn: depths in the chosen reference and unit. Data stays in MD."""
        if self._view is None:
            self._view = DepthView(self.well, self.depth_reference, self.display_unit, self.curve_units)
        return self._view

    def set_depth_reference(self, reference: str) -> None:
        """Draws the well against MD, TVD or TVDSS."""
        self.depth_reference = reference
        self._view = None
        self.layoutChanged.emit()

    def set_display_unit(self, unit: str | None) -> None:
        """Depth unit of the display ("m", "ft"; None = the file's unit)."""
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

    @staticmethod
    def _converter(old: str | None, new: str | None):
        def conv(v):
            if v is None:
                return None
            try:
                return float(f"{float(units.convert(v, old, new)):.6g}")
            except ValueError:
                return v

        return conv

    @staticmethod
    def _convert_track(track: TrackSpec, mnemonic: str, conv) -> None:
        """Rewrites the scales of a curve and the fixed fill values that are compared with it."""
        for c in track.curves:
            if c.mnemonic == mnemonic:
                c.left, c.right = conv(c.left), conv(c.right)
        for f in track.fills:
            if f.left_value is not None and f.right_curve == mnemonic:
                f.left_value = conv(f.left_value)
            if f.right_value is not None and f.left_curve == mnemonic:
                f.right_value = conv(f.right_value)

    def _convert_scales(self, mnemonic: str, old: str | None, new: str | None) -> None:
        """Rewrites track scales and fixed fill values of a curve from one unit to another."""
        conv = self._converter(old, new)
        for track in self.layout.tracks:
            self._convert_track(track, mnemonic, conv)
            for c in track.curves:
                if c.mnemonic == mnemonic:
                    c.unit = new

    def set_curve_unit(self, mnemonic: str, unit: str | None, notify: bool = True) -> None:
        """Displays a curve in another unit (None = back to the file unit)."""
        with self._untracked():
            self._set_curve_unit(mnemonic, unit, notify)

    def _set_curve_unit(self, mnemonic: str, unit: str | None, notify: bool) -> None:
        curve = self.well.curves.get(mnemonic)
        current = self.curve_units.get(mnemonic)
        target = unit or current
        if curve is None or target is None:
            return
        source = display_source_unit(curve, target)  # unit of the stored values
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
        with self._untracked():
            for mnem, curve in self.well.curves.items():
                target = units.system_unit(curve.unit, system)
                if target is None and system != "file" and mnem not in self.curve_units:
                    continue
                self._set_curve_unit(mnem, target, notify=False)
            self.display_unit = units.SYSTEM_DEPTH_UNIT.get(system)
            self._view = None
            self.layoutChanged.emit()

    def adopt_layout(self, layout: LogLayout) -> LogLayout:
        """Converts a layout's scales (written in each style's unit) to this well's display units."""
        for track in layout.tracks:
            for c in track.curves:
                target = self.display_unit_of(c.mnemonic)
                if c.unit and target and units.normalize(c.unit) != units.normalize(target):
                    self._convert_track(track, c.mnemonic, self._converter(c.unit, target))
                for same in track.curves:
                    if same.mnemonic == c.mnemonic:
                        same.unit = target
        return layout

    def style_for(self, mnemonic: str):
        """Default style for a curve, with its scale in the curve's display unit."""
        from innopetrol.model.layout import LogLayout as _Layout
        from innopetrol.model.layout import TrackSpec as _Track
        from innopetrol.model.mnemonics import make_curve_style

        style = make_curve_style(self.well, mnemonic)
        self.adopt_layout(_Layout([_Track(curves=[style])]))
        return style

    def set_survey(self, survey, elevation: float | None, location=False) -> None:
        """Survey, elevation and (unless `location` is False) the surface location."""
        with self.undo_step(_("Change survey and elevation")):
            if location is not False:
                self.well.location = location
            self._set_survey(survey, elevation)

    def _set_survey(self, survey, elevation: float | None) -> None:
        self.well.survey = survey
        self.well.elevation = elevation
        self._view = None
        if self.depth_reference == "tvdss" and elevation is None:
            self.depth_reference = "tvd"
        self.layoutChanged.emit()

    def set_layout(self, layout: LogLayout, text: str | None = None) -> None:
        with self.undo_step(text or _("Change layout")):
            self.layout = layout
            self.layoutChanged.emit()

    def set_track(self, index: int, track: TrackSpec) -> None:
        with self.undo_step(_("Edit track “{title}”").format(title=track.title)):
            self.layout.tracks[index] = track
            self.layoutChanged.emit()

    def insert_track(self, index: int, track: TrackSpec) -> None:
        with self.undo_step(_("Add track")):
            self.layout.tracks.insert(index, track)
            self.layoutChanged.emit()

    def remove_track(self, index: int) -> None:
        if 0 <= index < len(self.layout.tracks):
            with self.undo_step(_("Remove track “{title}”").format(title=self.layout.tracks[index].title)):
                del self.layout.tracks[index]
                self.layoutChanged.emit()

    def move_track(self, index: int, delta: int) -> int:
        j = index + delta
        if 0 <= index < len(self.layout.tracks) and 0 <= j < len(self.layout.tracks):
            with self.undo_step(_("Move track")):
                t = self.layout.tracks
                t[index], t[j] = t[j], t[index]
                self.layoutChanged.emit()
            return j
        return index

    def add_curves(self, curves: list[Curve]) -> None:
        with self.undo_step(_("Add curves")):
            for c in curves:
                self.well.add_curve(c)
            self.curvesChanged.emit()
            self.layoutChanged.emit()

    def remove_curve(self, mnemonic: str) -> None:
        with self.undo_step(_("Delete curve {name}").format(name=mnemonic)):
            self.well.remove_curve(mnemonic)
            self.curve_units.pop(mnemonic, None)
            for t in self.layout.tracks:
                t.curves = [c for c in t.curves if c.mnemonic != mnemonic]
                t.fills = [f for f in t.fills if mnemonic not in (f.left_curve, f.right_curve)]
            self._view = None
            self.curvesChanged.emit()
            self.layoutChanged.emit()

    def set_intervals(self, intervals: list[Interval], text: str | None = None) -> None:
        with self.undo_step(text or _("Edit intervals")):
            self.well.intervals = sorted(intervals, key=lambda i: i.top)
            self.topsChanged.emit()  # the tree and the views treat intervals like tops
            self.layoutChanged.emit()

    def set_tops(self, tops, text: str | None = None) -> None:
        with self.undo_step(text or _("Edit formation tops")):
            self.well.tops = sorted(tops, key=lambda t: t.depth)
            self.topsChanged.emit()
            self.layoutChanged.emit()
