"""WellDocument: an open well plus its layout, with signals so views can update themselves."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from innopetrol.model.layout import LogLayout, TrackSpec
from innopetrol.model.petro import PetroParams
from innopetrol.model.well import Curve, Well


class WellDocument(QObject):
    layoutChanged = Signal()
    curvesChanged = Signal()
    topsChanged = Signal()
    cursorMoved = Signal(float)  # depth under the cursor (NaN = outside)

    def __init__(self, well: Well, layout: LogLayout, petro: PetroParams | None = None, parent=None):
        super().__init__(parent)
        self.well = well
        self.layout = layout
        self.petro = petro

    @property
    def title(self) -> str:
        return self.well.name

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
