"""WellView: a well window (LogCanvas + scroll bars + context menu)."""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QGridLayout, QInputDialog, QMenu, QMessageBox, QScrollBar, QWidget

from innopetrol.i18n import _, pgettext
from innopetrol.model.layout import LogLayout, TrackSpec
from innopetrol.model.mnemonics import build_volumes_track
from innopetrol.model.scales import SCALE_PRESETS
from innopetrol.model.tops import PALETTE, Top
from innopetrol.render.scene import total_width
from innopetrol.ui.document import WellDocument
from innopetrol.ui.log_canvas import LogCanvas


class WellView(QWidget):
    statusMessage = Signal(str)
    exportRequested = Signal()
    closed = Signal(object)
    statsRequested = Signal(object, object)  # (document, (top, base) in MD): statistics of an interval

    def __init__(self, doc: WellDocument, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.canvas = LogCanvas(doc, self)
        self.vbar = QScrollBar(Qt.Orientation.Vertical, self)
        self.hbar = QScrollBar(Qt.Orientation.Horizontal, self)
        lay = QGridLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.canvas, 0, 0)
        lay.addWidget(self.vbar, 0, 1)
        lay.addWidget(self.hbar, 1, 0)
        self.setWindowTitle(doc.title)
        self._syncing = False

        self.canvas.viewChanged.connect(self._sync_bars)
        self.vbar.valueChanged.connect(self._vbar_moved)
        self.hbar.valueChanged.connect(self._hbar_moved)
        self.canvas.trackActivated.connect(self.edit_track)
        self.canvas.contextRequested.connect(self._context_menu)
        doc.cursorMoved.connect(self._cursor_moved)

    # ------------------------------------------------------------------ scroll

    def _sync_bars(self):
        self._syncing = True
        c = self.canvas
        lo, hi = c.scroll_range()
        self.vbar.setRange(0, int((hi - lo) * c.ppu))
        self.vbar.setPageStep(int(c.body_h))
        self.vbar.setSingleStep(20)
        self.vbar.setValue(int((c.top - lo) * c.ppu))
        extra = max(0, int(total_width(self.doc.layout) - c.width()))
        self.hbar.setRange(0, extra)
        self.hbar.setPageStep(max(c.width(), 1))
        self.hbar.setValue(int(c.x_offset))
        self.hbar.setVisible(extra > 0)
        self._syncing = False

    def _vbar_moved(self, v):
        if not self._syncing:
            lo, _hi = self.canvas.scroll_range()
            self.canvas.set_top(lo + v / self.canvas.ppu)

    def _hbar_moved(self, v):
        if not self._syncing:
            self.canvas.x_offset = v
            self.canvas.update()

    def _cursor_moved(self, md: float):
        if not math.isnan(md):
            self.statusMessage.emit(self.canvas.readout(md))

    # ------------------------------------------------------------------ track actions

    def edit_track(self, index: int | None = None):
        from innopetrol.ui.track_editor import TrackEditor

        index = self.canvas.selected if index is None or index is False else index
        if index is None or index < 0:
            return
        track = self.doc.layout.tracks[index]
        if track.is_depth:
            name, ok = QInputDialog.getText(self, _("Depth track"), _("Title:"), text=track.title)
            if ok:
                with self.doc.undo_step(_("Rename track")):
                    track.title = name
                    self.doc.layoutChanged.emit()
            return
        TrackEditor(self.doc, index, self).exec()

    def add_track(self, kind: str = "curves", after: int | None = None):
        after = self.canvas.selected if after is None else after
        index = (after + 1) if after is not None and after >= 0 else len(self.doc.layout.tracks)
        track: TrackSpec | None
        if kind == "depth":
            track = TrackSpec(kind="depth", title=pgettext("track title", "Depth"), width=72)
        elif kind == "intervals":
            track = TrackSpec(kind="intervals", title=_("Intervals"), width=110, grid="none")
        elif kind == "volumes":
            track = build_volumes_track(self.doc.well)
            if track is None:
                QMessageBox.information(
                    self, _("Volumes track"), _("The volumes track needs VSH and VMAT: run Well ▸ Petrophysics first.")
                )
                return
            self.doc.adopt_layout(LogLayout([track]))
        else:
            track = TrackSpec(title=_("Track {number}").format(number=index + 1))
        self.doc.insert_track(index, track)
        self.canvas.selected = index
        if kind == "curves":
            self.edit_track(index)

    def remove_track(self, index: int | None = None):
        index = self.canvas.selected if index is None else index
        if index is None or index < 0:
            return
        track = self.doc.layout.tracks[index]
        if track.curves:
            r = QMessageBox.question(
                self, _("Remove track"), _("Remove the track “{title}” and its settings?").format(title=track.title)
            )
            if r != QMessageBox.StandardButton.Yes:
                return
        self.canvas.selected = -1
        self.doc.remove_track(index)

    def move_track(self, delta: int):
        i = self.canvas.selected
        if i >= 0:
            self.canvas.selected = self.doc.move_track(i, delta)
            self.canvas.update()

    def rename_track(self, index: int | None = None):
        index = self.canvas.selected if index is None else index
        if index is None or index < 0:
            return
        track = self.doc.layout.tracks[index]
        name, ok = QInputDialog.getText(self, _("Rename track"), _("Title:"), text=track.title)
        if ok:
            with self.doc.undo_step(_("Rename track")):
                track.title = name
                self.doc.layoutChanged.emit()

    def add_top_at(self, depth: float):
        """Adds a top at a display depth; tops are always stored in measured depth."""
        view = self.doc.view
        md = float(view.to_md(depth))
        label = f"{view.depth_mnemonic} {depth:.2f} {view.depth_unit}"
        if view.reference != "md" or view.depth_unit != self.doc.well.depth_unit:
            label += f" (MD {md:.2f} {self.doc.well.depth_unit})"
        name, ok = QInputDialog.getText(self, _("New top"), _("Name of the top at {depth}:").format(depth=label))
        if ok and name.strip():
            tops = list(self.doc.well.tops)
            tops.append(Top(name.strip(), round(md, 2), PALETTE[len(tops) % len(PALETTE)]))
            self.doc.set_tops(tops, _("Add top {name}").format(name=name.strip()))

    # ------------------------------------------------------------------ context menu

    def scale_menu(self, parent: QWidget) -> QMenu:
        menu = QMenu(_("Vertical scale"), parent)
        fit = menu.addAction(_("Fit to window"))
        fit.setCheckable(True)
        fit.setChecked(self.canvas.fit_mode)
        fit.triggered.connect(self.canvas.fit)
        menu.addSeparator()
        current = self.canvas.current_scale()
        for n in SCALE_PRESETS:
            a = menu.addAction(f"1:{n}")
            a.setCheckable(True)
            a.setChecked(not self.canvas.fit_mode and abs(current - n) / n < 0.01)
            a.triggered.connect(lambda _checked=False, n=n: self.canvas.set_scale(n))
        return menu

    def _context_menu(self, index: int, depth: float, global_pos):
        menu = QMenu(self)
        if index >= 0:
            track = self.doc.layout.tracks[index]
            edit = menu.addAction(_("Edit track…") if not track.is_depth else _("Track title…"))
            edit.triggered.connect(lambda: self.edit_track(index))
            menu.addAction(_("Rename…")).triggered.connect(lambda: self.rename_track(index))
            left = menu.addAction(_("Move left"))
            left.setEnabled(index > 0)
            left.triggered.connect(lambda: self.move_track(-1))
            right = menu.addAction(_("Move right"))
            right.setEnabled(index < len(self.doc.layout.tracks) - 1)
            right.triggered.connect(lambda: self.move_track(1))
            menu.addAction(_("Remove track")).triggered.connect(lambda: self.remove_track(index))
            menu.addSeparator()
        menu.addAction(_("Add curve track")).triggered.connect(lambda: self.add_track("curves", index))
        menu.addAction(_("Add depth track")).triggered.connect(lambda: self.add_track("depth", index))
        menu.addAction(_("Add volumes track (lithology / fluids)")).triggered.connect(
            lambda: self.add_track("volumes", index)
        )
        menu.addAction(_("Add intervals track (perforations, tests, comments)")).triggered.connect(
            lambda: self.add_track("intervals", index)
        )
        if self.canvas.interval is not None:
            self._selection_menu(menu)
        if not math.isnan(depth):
            menu.addSeparator()
            add_top = QAction(_("Add top at {depth}…").format(depth=f"{depth:.2f}"), menu)
            add_top.triggered.connect(lambda: self.add_top_at(depth))
            menu.addAction(add_top)
        menu.addSeparator()
        menu.addMenu(self.scale_menu(menu))
        menu.addAction(_("Export image / PDF…")).triggered.connect(self.exportRequested.emit)
        menu.exec(global_pos)

    # ------------------------------------------------------------------ selected interval

    def selection_md(self) -> tuple[float, float] | None:
        """The interval selected on the log, in measured depth (how the data is stored)."""
        if self.canvas.interval is None:
            return None
        view = self.doc.view
        top, base = (float(view.to_md(d)) for d in self.canvas.interval)
        return (min(top, base), max(top, base))

    def _selection_menu(self, menu: QMenu) -> None:
        sel = menu.addMenu(_("Selected interval"))
        sel.addAction(_("Statistics and histogram…")).triggered.connect(
            lambda: self.statsRequested.emit(self.doc, self.selection_md())
        )
        sel.addAction(_("Zoom to the selection")).triggered.connect(self.canvas.zoom_to_interval)
        sel.addAction(_("Add as an interval (perforation, test, comment…)…")).triggered.connect(
            self.add_interval_from_selection
        )
        sel.addAction(_("Create a zone (tops at its top and base)…")).triggered.connect(self.zone_from_selection)
        sel.addAction(_("Export the selection (LAS / CSV)…")).triggered.connect(self.export_selection)
        sel.addSeparator()
        sel.addAction(_("Clear the selection (Esc)")).triggered.connect(lambda: self.canvas.set_interval(None))

    def add_interval_from_selection(self) -> None:
        from innopetrol.model.intervals import Interval
        from innopetrol.ui.intervals_dialog import IntervalsDialog

        md = self.selection_md()
        if md is not None:
            IntervalsDialog(self.doc, self, new=Interval(round(md[0], 2), round(md[1], 2), "perforation")).exec()

    def zone_from_selection(self) -> None:
        md = self.selection_md()
        if md is None:
            return
        name, ok = QInputDialog.getText(self, _("New zone"), _("Name of the zone:"))
        if not ok or not name.strip():
            return
        name = name.strip()
        tops = [t for t in self.doc.well.tops if t.name not in (name, _("Base of {zone}").format(zone=name))]
        color = PALETTE[len(tops) % len(PALETTE)]
        tops.append(Top(name, round(md[0], 2), color))
        # The zone ends at the next top; a "base" top is added only if none closes it already.
        if not any(md[0] < t.depth <= md[1] + 1e-9 for t in tops if t.name != name):
            tops.append(Top(_("Base of {zone}").format(zone=name), round(md[1], 2), color))
        self.doc.set_tops(tops, _("Create zone {name}").format(name=name))

    def export_selection(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        md = self.selection_md()
        if md is None:
            return
        path, chosen = QFileDialog.getSaveFileName(
            self, _("Export the selection"), f"{self.doc.title}_{md[0]:g}-{md[1]:g}.las", "LAS (*.las);;CSV (*.csv)"
        )
        if not path:
            return
        mask = self.doc.well.interval_mask(*md)
        try:
            if path.lower().endswith(".csv") or chosen.startswith("CSV"):
                self.doc.well.to_csv(path, mask)
            else:
                self.doc.well.to_las(path, mask)
        except OSError as e:
            QMessageBox.warning(self, _("Export the selection"), _("Could not export: {error}").format(error=e))
            return
        self.statusMessage.emit(_("Exported {count} samples to {path}").format(count=int(mask.sum()), path=path))

    def closeEvent(self, e):
        # Closing the window loses nothing: the well stays loaded and in the project.
        e.accept()
        self.closed.emit(self.doc)
