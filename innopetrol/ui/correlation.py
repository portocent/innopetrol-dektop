"""Correlación multi-pozo: pozos lado a lado, misma escala, opcionalmente aplanados en un tope."""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QScrollArea, QScrollBar, QVBoxLayout, QWidget)

from innopetrol.model.scales import SCALE_PRESETS
from innopetrol.render.scene import total_width
from innopetrol.resources import app_icon
from innopetrol.ui.document import WellDocument
from innopetrol.ui.log_canvas import LogCanvas

DEPTH_DATUM = "__depth__"
TITLE_H = 26


class CorrelationSetup(QDialog):
    """Elegir pozos y tope de aplanamiento."""

    def __init__(self, docs: list[WellDocument], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Correlación de pozos")
        self.setWindowIcon(app_icon())
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Pozos a correlacionar (en orden):"))
        self.list = QListWidget()
        for d in docs:
            item = QListWidgetItem(d.title)
            item.setData(Qt.UserRole, d)
            item.setCheckState(Qt.Checked)
            self.list.addItem(item)
        self.list.setDragDropMode(QListWidget.InternalMove)
        lay.addWidget(self.list)
        self.datum = QComboBox()
        self.datum.addItem("Profundidad medida (sin aplanar)", DEPTH_DATUM)
        names = sorted({t.name for d in docs for t in d.well.tops})
        for n in names:
            self.datum.addItem(f"Aplanar en tope: {n}", n)
        lay.addWidget(QLabel("Datum:"))
        lay.addWidget(self.datum)
        self.tracks = QComboBox()
        self.tracks.addItem("Primeros 3 tracks (correlación, profundidad, resistividad)", 3)
        self.tracks.addItem("Primeros 2 tracks", 2)
        self.tracks.addItem("Todos los tracks", 0)
        lay.addWidget(QLabel("Tracks de cada pozo:"))
        lay.addWidget(self.tracks)
        if not names:
            hint = QLabel("Para aplanar, defina topes con el mismo nombre en cada pozo (Pozo ▸ Topes).")
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
    """Une con líneas los topes del mismo nombre entre dos pozos vecinos."""

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


def compact_doc(doc: WellDocument, n_tracks: int, parent) -> WellDocument:
    """Vista reducida del pozo para correlación: comparte el pozo pero con menos tracks."""
    if not n_tracks:
        return doc
    layout = doc.layout.copy()
    layout.tracks = layout.tracks[:n_tracks]
    view = WellDocument(doc.well, layout, parent=parent)
    doc.topsChanged.connect(view.layoutChanged)  # topes editados en el pozo se ven en la correlación
    doc.layoutChanged.connect(view.layoutChanged)
    return view


class CorrelationWindow(QDialog):
    def __init__(self, docs: list[WellDocument], datum: str, parent=None, n_tracks: int = 3):
        super().__init__(parent)
        self.setWindowTitle("Correlación — " + " · ".join(d.title for d in docs))
        self.setWindowIcon(app_icon())
        self.setModal(False)
        self.resize(1200, 760)
        self.datum = datum
        self._sync = False
        docs = [compact_doc(d, n_tracks, self) for d in docs]

        root = QVBoxLayout(self)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Escala:"))
        self.scale = QComboBox()
        self.scale.addItem("Ajustar", 0)
        for n in SCALE_PRESETS:
            self.scale.addItem(f"1:{n}", n)
        self.scale.setCurrentIndex(self.scale.findData(500))
        bar.addWidget(self.scale)
        info = "Aplanado en «%s»" % datum if datum != DEPTH_DATUM else "Profundidad medida"
        bar.addWidget(QLabel(f"   Datum: {info}.   Rueda: desplazar · Ctrl+rueda: zoom"))
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
        top = next((t for t in d.well.tops if t.name == self.datum), None)
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
        QTimer.singleShot(0, self._apply_scale)  # cuando los widgets ya tienen su tamaño final

    # rango combinado en coordenadas de visualización (profundidad + desplazamiento)
    def _display_range(self) -> tuple[float, float]:
        lo = min(c.well.start + c.depth_shift for c in self.canvases)
        hi = max(c.well.stop + c.depth_shift for c in self.canvases)
        return lo, hi

    def _apply_scale(self):
        ref = self.canvases[0]
        n = self.scale.currentData()
        lo, hi = self._display_range()
        if n:
            ref.set_scale(n)
            if self.datum != DEPTH_DATUM:
                ref.set_view(-ref.body_h / ref.ppu / 2, ref.ppu)  # datum centrado
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
        for c in self.canvases:
            if c is not source:
                c.set_view(source.top, source.ppu)
        for conn in self.findChildren(TopConnector):
            conn.update()
        lo, hi = self._display_range()
        ppu = source.ppu
        pad = 50 / ppu
        self.vbar.setRange(int((lo - pad) * ppu), int(max(lo - pad, hi + pad - source.body_h / ppu) * ppu))
        self.vbar.setPageStep(int(source.body_h))
        self.vbar.setValue(int(source.top * ppu))
        self._sync = False

    def _vbar_moved(self, v):
        if self._sync:
            return
        ref = self.canvases[0]
        ref.set_view(v / ref.ppu, ref.ppu)
        self._propagate(ref)
