"""WellView: ventana de un pozo (LogCanvas + barras de desplazamiento + menú contextual)."""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QGridLayout, QInputDialog, QMenu, QMessageBox, QScrollBar, QWidget

from innopetrol.model.layout import TrackSpec
from innopetrol.model.scales import SCALE_PRESETS
from innopetrol.model.tops import PALETTE, Top
from innopetrol.render.scene import total_width
from innopetrol.ui.document import WellDocument
from innopetrol.ui.log_canvas import LogCanvas


class WellView(QWidget):
    statusMessage = Signal(str)
    exportRequested = Signal()
    closed = Signal(object)

    def __init__(self, doc: WellDocument, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.canvas = LogCanvas(doc, self)
        self.vbar = QScrollBar(Qt.Vertical, self)
        self.hbar = QScrollBar(Qt.Horizontal, self)
        lay = QGridLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.canvas, 0, 0)
        lay.addWidget(self.vbar, 0, 1)
        lay.addWidget(self.hbar, 1, 0)
        self.setWindowTitle(doc.title)
        self._syncing = False
        self.confirm_close = True

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
            lo, _ = self.canvas.scroll_range()
            self.canvas.set_top(lo + v / self.canvas.ppu)

    def _hbar_moved(self, v):
        if not self._syncing:
            self.canvas.x_offset = v
            self.canvas.update()

    def _cursor_moved(self, depth: float):
        if not math.isnan(depth):
            self.statusMessage.emit(self.canvas.readout(depth))

    # ------------------------------------------------------------------ acciones sobre tracks

    @property
    def selected_track(self) -> int:
        return self.canvas.selected

    def edit_track(self, index: int | None = None):
        from innopetrol.ui.track_editor import TrackEditor

        index = self.canvas.selected if index is None or index is False else index
        if index is None or index < 0:
            return
        track = self.doc.layout.tracks[index]
        if track.is_depth:
            name, ok = QInputDialog.getText(self, "Track de profundidad", "Título:", text=track.title)
            if ok:
                track.title = name
                self.doc.layoutChanged.emit()
            return
        TrackEditor(self.doc, index, self).exec()

    def add_track(self, kind: str = "curves", after: int | None = None):
        after = self.canvas.selected if after is None else after
        index = (after + 1) if after is not None and after >= 0 else len(self.doc.layout.tracks)
        if kind == "depth":
            track = TrackSpec(kind="depth", title="Prof.", width=72)
        else:
            track = TrackSpec(title=f"Track {index + 1}")
        self.doc.insert_track(index, track)
        self.canvas.selected = index
        if kind != "depth":
            self.edit_track(index)

    def remove_track(self, index: int | None = None):
        index = self.canvas.selected if index is None else index
        if index is None or index < 0:
            return
        track = self.doc.layout.tracks[index]
        if track.curves:
            r = QMessageBox.question(self, "Eliminar track", f"¿Eliminar el track «{track.title}» y su configuración?")
            if r != QMessageBox.Yes:
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
        name, ok = QInputDialog.getText(self, "Renombrar track", "Título:", text=track.title)
        if ok:
            track.title = name
            self.doc.layoutChanged.emit()

    def add_top_at(self, depth: float):
        name, ok = QInputDialog.getText(self, "Nuevo tope", f"Nombre del tope a {depth:.2f} {self.doc.well.depth_unit}:")
        if ok and name.strip():
            tops = list(self.doc.well.tops)
            tops.append(Top(name.strip(), round(depth, 2), PALETTE[len(tops) % len(PALETTE)]))
            self.doc.set_tops(tops)

    # ------------------------------------------------------------------ menú contextual

    def scale_menu(self, parent: QWidget) -> QMenu:
        menu = QMenu("Escala vertical", parent)
        fit = menu.addAction("Ajustar a la ventana")
        fit.setCheckable(True)
        fit.setChecked(self.canvas.fit_mode)
        fit.triggered.connect(self.canvas.fit)
        menu.addSeparator()
        current = self.canvas.current_scale()
        for n in SCALE_PRESETS:
            a = menu.addAction(f"1:{n}")
            a.setCheckable(True)
            a.setChecked(not self.canvas.fit_mode and abs(current - n) / n < 0.01)
            a.triggered.connect(lambda _=False, n=n: self.canvas.set_scale(n))
        return menu

    def _context_menu(self, index: int, depth: float, global_pos):
        menu = QMenu(self)
        if index >= 0:
            track = self.doc.layout.tracks[index]
            edit = menu.addAction("Editar track…" if not track.is_depth else "Título del track…")
            edit.triggered.connect(lambda: self.edit_track(index))
            menu.addAction("Renombrar…").triggered.connect(lambda: self.rename_track(index))
            left = menu.addAction("Mover a la izquierda")
            left.setEnabled(index > 0)
            left.triggered.connect(lambda: self.move_track(-1))
            right = menu.addAction("Mover a la derecha")
            right.setEnabled(index < len(self.doc.layout.tracks) - 1)
            right.triggered.connect(lambda: self.move_track(1))
            menu.addAction("Eliminar track").triggered.connect(lambda: self.remove_track(index))
            menu.addSeparator()
        menu.addAction("Agregar track de curvas").triggered.connect(lambda: self.add_track("curves", index))
        menu.addAction("Agregar track de profundidad").triggered.connect(lambda: self.add_track("depth", index))
        if not math.isnan(depth):
            menu.addSeparator()
            add_top = QAction(f"Agregar tope en {depth:.2f}…", menu)
            add_top.triggered.connect(lambda: self.add_top_at(depth))
            menu.addAction(add_top)
        menu.addSeparator()
        menu.addMenu(self.scale_menu(menu))
        menu.addAction("Exportar imagen / PDF…").triggered.connect(self.exportRequested.emit)
        menu.exec(global_pos)

    def closeEvent(self, e):
        if self.confirm_close:
            r = QMessageBox.question(self, "Cerrar pozo", f"¿Está seguro de cerrar el pozo «{self.doc.title}»?")
            if r != QMessageBox.Yes:  # antes: retval == 1024 (número mágico)
                e.ignore()
                return
        e.accept()
        self.closed.emit(self.doc)
