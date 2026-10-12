"""Multi-well correlation: wells side by side at the same scale, optionally flattened on a top."""

from __future__ import annotations

import sys

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QScrollArea, QScrollBar, QVBoxLayout, QWidget)

from innopetrol.i18n import _
from innopetrol.model.scales import MM_PER_UNIT, SCALE_PRESETS
from innopetrol.render.scene import total_width
from innopetrol.resources import app_icon
from innopetrol.ui.document import WellDocument
from innopetrol.ui.log_canvas import LogCanvas

DEPTH_DATUM = "__depth__"
TITLE_H = 26


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
        root.addLayout(bar)

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
        for c in self.canvases:
            c.min_header_h = header
            c.viewChanged.connect(lambda c=c: self._propagate(c))
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
