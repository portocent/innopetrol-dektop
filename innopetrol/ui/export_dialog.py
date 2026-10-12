"""Diálogo de exportación: imagen/PDF del registro, LAS y CSV."""

from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout,
                               QMessageBox, QSpinBox)

from innopetrol.model.scales import SCALE_PRESETS
from innopetrol.render.export import ExportError, export_pdf, export_png
from innopetrol.resources import app_icon
from innopetrol.ui.document import WellDocument


class ExportDialog(QDialog):
    def __init__(self, doc: WellDocument, visible: tuple[float, float] | None, scale: float | None, parent=None):
        super().__init__(parent)
        self.doc = doc
        w = doc.well
        self.setWindowTitle(f"Exportar registro — {doc.title}")
        self.setWindowIcon(app_icon())
        form = QFormLayout(self)
        self.fmt = QComboBox()
        self.fmt.addItem("PDF (paginado, para imprimir)", "pdf")
        self.fmt.addItem("Imagen PNG", "png")
        self.scale = QComboBox()
        for n in SCALE_PRESETS:
            self.scale.addItem(f"1:{n}", n)
        nearest = min(SCALE_PRESETS, key=lambda n: abs(n - (scale or 500)))
        self.scale.setCurrentIndex(self.scale.findData(nearest))
        self.top = QDoubleSpinBox(decimals=2, minimum=w.start, maximum=w.stop)
        self.base = QDoubleSpinBox(decimals=2, minimum=w.start, maximum=w.stop)
        self.top.setValue(w.start)
        self.base.setValue(w.stop)
        self.interval = QComboBox()
        self.interval.addItem("Pozo completo", (w.start, w.stop))
        if visible:
            v0, v1 = max(visible[0], w.start), min(visible[1], w.stop)
            self.interval.addItem("Lo visible en pantalla", (v0, v1))
        for t in w.tops:
            nxt = next((o.depth for o in w.tops if o.depth > t.depth), w.stop)
            self.interval.addItem(f"Zona {t.name}", (t.depth, nxt))
        self.interval.currentIndexChanged.connect(self._interval)
        self.page = QComboBox()
        for p in ("A4", "Letter", "A3"):
            self.page.addItem(p, p)
        self.dpi = QSpinBox()
        self.dpi.setRange(72, 600)
        self.dpi.setValue(200)
        form.addRow("Formato:", self.fmt)
        form.addRow("Escala vertical:", self.scale)
        form.addRow("Intervalo:", self.interval)
        form.addRow(f"Desde ({w.depth_unit}):", self.top)
        form.addRow(f"Hasta ({w.depth_unit}):", self.base)
        form.addRow("Papel (PDF):", self.page)
        form.addRow("Resolución (PNG, dpi):", self.dpi)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Exportar…")
        buttons.accepted.connect(self._export)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _interval(self):
        a, b = self.interval.currentData()
        self.top.setValue(a)
        self.base.setValue(b)

    def _export(self):
        top, base = self.top.value(), self.base.value()
        if base <= top:
            QMessageBox.warning(self, "Exportar", "«Hasta» debe ser mayor que «Desde».")
            return
        kind = self.fmt.currentData()
        ext = "pdf" if kind == "pdf" else "png"
        scale = self.scale.currentData()
        path, _ = QFileDialog.getSaveFileName(self, "Guardar como", f"{self.doc.title}_1-{scale}.{ext}",
                                              f"{ext.upper()} (*.{ext})")
        if not path:
            return
        try:
            if kind == "pdf":
                pages = export_pdf(path, self.doc.well, self.doc.layout, scale, top, base, page=self.page.currentData())
                msg = f"PDF guardado ({pages} hoja{'s' if pages != 1 else ''})."
            else:
                export_png(path, self.doc.well, self.doc.layout, scale, top, base, dpi=self.dpi.value())
                msg = "Imagen guardada."
        except (ExportError, OSError) as e:
            QMessageBox.warning(self, "Exportar", f"No se pudo exportar: {e}")
            return
        QMessageBox.information(self, "Exportar", msg)
        self.accept()
