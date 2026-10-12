"""Multi-well correlation: wells side by side at the same scale, optionally flattened on a top."""

from __future__ import annotations

import sys

import shiboken6
from PySide6.QtCore import QEvent, QPointF, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QKeySequence, QPainter, QPen
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QInputDialog, QLabel, QListWidget,
                               QListWidgetItem, QMenu, QPushButton, QScrollArea, QScrollBar, QVBoxLayout, QWidget)

from innopetrol.i18n import _
from innopetrol.model.scales import MM_PER_UNIT, SCALE_PRESETS
from innopetrol.model.tops import PALETTE, Top
from innopetrol.render.scene import total_width
from innopetrol.resources import app_icon
from innopetrol.ui.document import WellDocument
from innopetrol.ui.log_canvas import LogCanvas

DEPTH_DATUM = "__depth__"
TITLE_H = 26
TOP_GRAB_PX = 8  # how close to a top line a right-click must be to offer removing it


class CorrelationSetup(QDialog):
    """Choose the wells and the flattening top."""

    def __init__(self, docs: list[WellDocument], parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Well correlation"))
        self.setWindowIcon(app_icon())
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(_("Wells to correlate (in order):")))
        self.list = QListWidget()
        for d in docs:
            item = QListWidgetItem(d.title)
            item.setData(Qt.UserRole, d)
            item.setCheckState(Qt.Checked)
            self.list.addItem(item)
        self.list.setDragDropMode(QListWidget.InternalMove)
        lay.addWidget(self.list)
        self.reference = QComboBox()
        self.reference.addItem(_("Measured depth (MD)"), "md")
        self.reference.addItem(_("True vertical depth (TVD)"), "tvd")
        if all(d.well.elevation is not None for d in docs):
            self.reference.addItem(_("True vertical depth subsea (TVDSS)"), "tvdss")
        if any(d.well.survey is not None for d in docs):
            # Deviated wells must be compared vertically, not along the hole.
            self.reference.setCurrentIndex(self.reference.count() - 1)
        lay.addWidget(QLabel(_("Depth reference:")))
        lay.addWidget(self.reference)
        self.datum = QComboBox()
        self.datum.addItem(_("No flattening (depth)"), DEPTH_DATUM)
        names = sorted({t.name for d in docs for t in d.well.tops})
        for n in names:
            self.datum.addItem(_("Flatten on top: {name}").format(name=n), n)
        lay.addWidget(QLabel(_("Datum:")))
        lay.addWidget(self.datum)
        self.tracks = QComboBox()
        self.tracks.addItem(_("First 3 tracks (correlation, depth, resistivity)"), 3)
        self.tracks.addItem(_("First 2 tracks"), 2)
        self.tracks.addItem(_("All tracks"), 0)
        lay.addWidget(QLabel(_("Tracks of each well:")))
        lay.addWidget(self.tracks)
        if not names:
            hint = QLabel(_("To flatten, define tops with the same name in every well (Well ▸ Tops)."))
            hint.setStyleSheet("color:#566573")
            hint.setWordWrap(True)
            lay.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def selected(self) -> list[WellDocument]:
        return [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())
                if self.list.item(i).checkState() == Qt.Checked]


class TopConnector(QWidget):
    """Draws lines joining tops with the same name in two neighboring wells."""

    def __init__(self, left: LogCanvas, right: LogCanvas, parent=None):
        super().__init__(parent)
        self.left, self.right = left, right
        self.setFixedWidth(46)

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#d5d8dc"))
        p.setRenderHint(QPainter.Antialiasing)
        top_y = self.left.header_h
        rights = {t.name: t for t in self.right.well.tops}
        for t in self.left.well.tops:
            other = rights.get(t.name)
            if other is None:
                continue
            y0, y1 = self.left.y_of(t.depth), self.right.y_of(other.depth)
            if max(y0, y1) < top_y or min(y0, y1) > self.height():
                continue
            p.setPen(QPen(QColor(t.color), 1.6, Qt.DashLine))
            p.drawLine(QPointF(0, max(y0, top_y)), QPointF(self.width(), max(y1, top_y)))
        p.end()


def compact_doc(doc: WellDocument, n_tracks: int, parent, reference: str = "md") -> WellDocument:
    """View of a well for correlation: shares the well data, with its own tracks and depth reference
    (so changing them here never alters the well's own window)."""
    layout = doc.layout.copy()
    if n_tracks:
        layout.tracks = layout.tracks[:n_tracks]
    view = WellDocument(doc.well, layout, parent=parent)
    view.depth_reference = reference
    view.display_unit = doc.display_unit
    doc.topsChanged.connect(view.layoutChanged)  # tops edited in the well show up in the correlation
    doc.layoutChanged.connect(view.layoutChanged)
    return view


class CorrelationWindow(QDialog):
    def __init__(self, docs: list[WellDocument], datum: str, parent=None, n_tracks: int = 3,
                 reference: str = "md"):
        super().__init__(parent)
        self.setWindowTitle(_("Correlation — {wells}").format(wells=" · ".join(d.title for d in docs)))
        self.setWindowIcon(app_icon())
        self.setModal(False)
        self.resize(1200, 760)
        self.datum = datum
        self._sync = False
        self.sources = list(docs)  # the wells' own documents: picked tops are saved there (with undo)
        self._picked: list[WellDocument] = []  # wells changed from this window, for its undo shortcut
        docs = [compact_doc(d, n_tracks, self, reference) for d in docs]

        root = QVBoxLayout(self)
        bar = QHBoxLayout()
        bar.addWidget(QLabel(_("Scale:")))
        self.scale = QComboBox()
        self.scale.addItem(_("Fit"), 0)
        for n in SCALE_PRESETS:
            self.scale.addItem(f"1:{n}", n)
        self.scale.setCurrentIndex(self.scale.findData(500))
        bar.addWidget(self.scale)
        info = reference.upper()
        if datum != DEPTH_DATUM:
            info += " · " + _("flattened on “{top}”").format(top=datum)
        bar.addWidget(QLabel("   " + _("Datum: {datum}.   Wheel: scroll · {modifier}+wheel: zoom").format(
            datum=info, modifier="⌘" if sys.platform == "darwin" else "Ctrl")))
        bar.addStretch()
        # Picking tops: choose (or type) a name, turn picking on and click on each well.
        bar.addWidget(QLabel(_("Top:")))
        self.top_name = QComboBox()
        self.top_name.setEditable(True)
        self.top_name.setMinimumWidth(160)
        self.top_name.lineEdit().setPlaceholderText(_("name of the top"))
        bar.addWidget(self.top_name)
        self.pick = QPushButton(_("Pick tops"))
        self.pick.setCheckable(True)
        self.pick.setToolTip(_("Click on a well to place the top there; clicking again moves it. "
                               "Right-click: more options."))
        self.pick.toggled.connect(self._pick_toggled)
        bar.addWidget(self.pick)
        undo = QAction(self)
        undo.setShortcut(QKeySequence.Undo)
        undo.triggered.connect(self.undo_pick)
        self.addAction(undo)
        root.addLayout(bar)
        self._refresh_names()

        body = QHBoxLayout()
        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setSpacing(0)
        row.setContentsMargins(0, 0, 0, 0)
        self.canvases: list[LogCanvas] = []
        for i, d in enumerate(docs):
            c = LogCanvas(d, show_top_labels=True)
            c.clamp_enabled = False
            c.fit_mode = False
            c.setFixedWidth(int(total_width(d.layout)) + 1)
            c.depth_shift = self._shift(d)
            self.canvases.append(c)
            if i:
                row.addWidget(self._column(None, TopConnector(self.canvases[i - 1], c)))
            row.addWidget(self._column(d.title, c))
        row.addStretch()
        self.area.setWidget(row_widget)
        body.addWidget(self.area, 1)
        self.vbar = QScrollBar(Qt.Vertical)
        body.addWidget(self.vbar)
        root.addLayout(body, 1)

        header = max(c.natural_header_h() for c in self.canvases)
        for i, c in enumerate(self.canvases):
            c.min_header_h = header
            c.viewChanged.connect(lambda c=c: self._propagate(c))
            c.installEventFilter(self)
            c.contextRequested.connect(lambda _track, depth, pos, i=i: self._context_menu(i, depth, pos))
            self.sources[i].topsChanged.connect(lambda i=i: self._tops_changed(i))
        self.vbar.valueChanged.connect(self._vbar_moved)
        self.scale.currentIndexChanged.connect(self._apply_scale)

    def _shift(self, d: WellDocument) -> float:
        if self.datum == DEPTH_DATUM:
            return 0.0
        top = next((t for t in d.view.tops if t.name == self.datum), None)  # in display depth
        return -top.depth if top else 0.0

    @staticmethod
    def _column(title: str | None, widget: QWidget) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(0)
        v.setContentsMargins(0, 0, 0, 0)
        label = QLabel(f"<b>{title}</b>" if title else "")
        label.setFixedHeight(TITLE_H)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("background:#2c3e50; color:white" if title else "background:#d5d8dc")
        v.addWidget(label)
        v.addWidget(widget, 1)
        return w

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, self._apply_scale)  # once the widgets have their final size

    # combined range in display coordinates (depth + shift)
    # The first well is the reference: display coordinates are in its depth unit. Each well
    # converts with `_factor` (its unit -> reference unit), so wells in feet and meters share
    # the same physical scale and line up at the same true depth.
    def _factor(self, c: LogCanvas) -> float:
        ref_unit = self.canvases[0].well.depth_unit
        return MM_PER_UNIT.get(c.well.depth_unit, 1000.0) / MM_PER_UNIT.get(ref_unit, 1000.0)

    def _display_range(self) -> tuple[float, float]:
        """Combined range in reference display coordinates (depth + shift, in the reference unit)."""
        lo = min((c.well.start + c.depth_shift) * self._factor(c) for c in self.canvases)
        hi = max((c.well.stop + c.depth_shift) * self._factor(c) for c in self.canvases)
        return lo, hi

    def _apply_scale(self):
        ref = self.canvases[0]
        n = self.scale.currentData()
        lo, hi = self._display_range()
        if n:
            ref.set_scale(n)
            if self.datum != DEPTH_DATUM:
                ref.set_view(-ref.body_h / ref.ppu / 2, ref.ppu)  # datum centered
            else:
                ref.set_view(lo, ref.ppu)
        else:
            ppu = ref.body_h / max(hi - lo, 1e-6)
            ref.set_view(lo, ppu)
        self._propagate(ref)

    def _propagate(self, source: LogCanvas):
        if self._sync:
            return
        self._sync = True
        f = self._factor(source)
        top, ppu = source.top * f, source.ppu / f  # in reference units
        for c in self.canvases:
            if c is not source:
                fc = self._factor(c)
                c.set_view(top / fc, ppu * fc)
        for conn in self.findChildren(TopConnector):
            conn.update()
        lo, hi = self._display_range()
        body_h = source.body_h
        pad = 50 / ppu
        self.vbar.setRange(int((lo - pad) * ppu), int(max(lo - pad, hi + pad - body_h / ppu) * ppu))
        self.vbar.setPageStep(int(body_h))
        self.vbar.setValue(int(top * ppu))
        self._sync = False

    def _vbar_moved(self, v):
        if self._sync:
            return
        ref = self.canvases[0]
        ref.set_view(v / ref.ppu, ref.ppu)
        self._propagate(ref)

    # ------------------------------------------------------------------ picking tops

    def _known_names(self) -> list[str]:
        return sorted({t.name for d in self.sources for t in d.well.tops}, key=str.lower)

    def _refresh_names(self):
        current = self.top_name.currentText()
        self.top_name.blockSignals(True)
        self.top_name.clear()
        self.top_name.addItems(self._known_names())
        self.top_name.setEditText(current)
        self.top_name.blockSignals(False)

    def _pick_toggled(self, on: bool):
        for c in self.canvases:
            c.setCursor(Qt.CrossCursor if on else Qt.ArrowCursor)
        if on and not self.top_name.currentText().strip():
            self.top_name.setFocus()

    def eventFilter(self, obj, e):
        if not shiboken6.isValid(self.pick):  # the window is being destroyed
            return False
        if (self.pick.isChecked() and e.type() == QEvent.MouseButtonPress and e.button() == Qt.LeftButton
                and obj in self.canvases and e.position().y() > obj.header_h):
            name = self.top_name.currentText().strip()
            if not name:
                self.top_name.setFocus()
                self.top_name.lineEdit().setPlaceholderText(_("type the name of the top first"))
                return True
            self.place_top(self.canvases.index(obj), obj.depth_at(e.position().y()), name)
            return True
        return super().eventFilter(obj, e)

    def place_top(self, index: int, depth: float, name: str) -> None:
        """Places (or moves) the top `name` in a well at a depth of its column (display reference)."""
        source, canvas = self.sources[index], self.canvases[index]
        md = round(float(canvas.well.to_md(depth)), 2)
        tops = list(source.well.tops)
        existing = next((t for t in tops if t.name == name), None)
        if existing is not None:
            tops = [Top(t.name, md, t.color) if t is existing else t for t in tops]
            text = _("Move top {name}").format(name=name)
        else:
            # The same name keeps the same color in every well, so the correlation lines read well.
            color = next((t.color for d in self.sources for t in d.well.tops if t.name == name),
                         PALETTE[len(self._known_names()) % len(PALETTE)])
            tops.append(Top(name, md, color))
            text = _("Add top {name}").format(name=name)
        source.set_tops(tops, text)
        self._picked.append(source)

    def remove_top(self, index: int, name: str) -> None:
        source = self.sources[index]
        source.set_tops([t for t in source.well.tops if t.name != name], _("Remove top {name}").format(name=name))
        self._picked.append(source)

    def undo_pick(self):
        """Undoes the last top change made from this window (each well keeps its own history)."""
        while self._picked:
            doc = self._picked.pop()
            if doc.undo_stack.canUndo():
                doc.undo_stack.undo()
                return

    def _near_top(self, index: int, depth: float) -> str | None:
        canvas = self.canvases[index]
        y = canvas.y_of(depth)
        best = min(canvas.well.tops, key=lambda t: abs(canvas.y_of(t.depth) - y), default=None)
        return best.name if best is not None and abs(canvas.y_of(best.depth) - y) <= TOP_GRAB_PX else None

    def _context_menu(self, index: int, depth: float, global_pos):
        if depth != depth:  # NaN: header area
            return
        menu = QMenu(self)
        name = self.top_name.currentText().strip()
        if name:
            menu.addAction(_("Place “{name}” here").format(name=name)).triggered.connect(
                lambda: self.place_top(index, depth, name))
        menu.addAction(_("New top here…")).triggered.connect(lambda: self._new_top(index, depth))
        near = self._near_top(index, depth)
        if near:
            menu.addSeparator()
            menu.addAction(_("Remove top “{name}”").format(name=near)).triggered.connect(
                lambda: self.remove_top(index, near))
        menu.exec(global_pos)

    def _new_top(self, index: int, depth: float):
        name, ok = QInputDialog.getItem(self, _("New top"), _("Name of the top:"), self._known_names(), 0, True)
        if ok and name.strip():
            self.top_name.setEditText(name.strip())
            self.place_top(index, depth, name.strip())

    def _tops_changed(self, index: int):
        """Tops edited here or in the well's window: names, flattening and connecting lines follow."""
        self._refresh_names()
        if self.datum != DEPTH_DATUM:
            canvas = self.canvases[index]
            shift = self._shift(canvas.doc)
            if shift != canvas.depth_shift:
                canvas.depth_shift = shift
                canvas.invalidate()
                self._propagate(self.canvases[0])
        for conn in self.findChildren(TopConnector):
            conn.update()
