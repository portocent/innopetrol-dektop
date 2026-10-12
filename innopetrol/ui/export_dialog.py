"""Export dialog: image/PDF of the log."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QMessageBox,
    QSpinBox,
)

from innopetrol.i18n import _, ngettext
from innopetrol.model.scales import SCALE_PRESETS
from innopetrol.render.export import ExportError, export_pdf, export_png
from innopetrol.resources import app_icon
from innopetrol.ui.document import WellDocument


class ExportDialog(QDialog):
    def __init__(self, doc: WellDocument, visible: tuple[float, float] | None, scale: float | None, parent=None):
        super().__init__(parent)
        self.doc = doc
        w = doc.view  # depths in the reference and unit being displayed
        self.setWindowTitle(_("Export log — {well}").format(well=doc.title))
        self.setWindowIcon(app_icon())
        form = QFormLayout(self)
        self.fmt = QComboBox()
        self.fmt.addItem(_("PDF (paginated, for printing)"), "pdf")
        self.fmt.addItem(_("PNG image"), "png")
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
        self.interval.addItem(_("Whole well"), (w.start, w.stop))
        if visible:
            v0, v1 = max(visible[0], w.start), min(visible[1], w.stop)
            self.interval.addItem(_("What is visible on screen"), (v0, v1))
        for t in w.tops:
            nxt = next((o.depth for o in w.tops if o.depth > t.depth), w.stop)
            self.interval.addItem(_("Zone {name}").format(name=t.name), (t.depth, nxt))
        self.interval.currentIndexChanged.connect(self._interval)
        self.page = QComboBox()
        for p in ("A4", "Letter", "A3"):
            self.page.addItem(p, p)
        self.dpi = QSpinBox()
        self.dpi.setRange(72, 600)
        self.dpi.setValue(200)
        form.addRow(_("Format:"), self.fmt)
        form.addRow(_("Vertical scale:"), self.scale)
        form.addRow(_("Interval:"), self.interval)
        form.addRow(_("From ({unit}):").format(unit=w.depth_unit), self.top)
        form.addRow(_("To ({unit}):").format(unit=w.depth_unit), self.base)
        form.addRow(_("Paper (PDF):"), self.page)
        form.addRow(_("Resolution (PNG, dpi):"), self.dpi)
        self.heading = QCheckBox(_("Log heading with the well data (company, field, elevation, survey…)"))
        self.heading.setChecked(True)
        form.addRow(self.heading)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(_("Export…"))
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
            QMessageBox.warning(self, _("Export"), _("“To” must be greater than “From”."))
            return
        kind = self.fmt.currentData()
        ext = "pdf" if kind == "pdf" else "png"
        scale = self.scale.currentData()
        path, _filter = QFileDialog.getSaveFileName(
            self, _("Save as"), f"{self.doc.title}_1-{scale}.{ext}", f"{ext.upper()} (*.{ext})"
        )
        if not path:
            return
        try:
            if kind == "pdf":
                pages = export_pdf(
                    path,
                    self.doc.view,
                    self.doc.layout,
                    scale,
                    top,
                    base,
                    page=self.page.currentData(),
                    heading=self.heading.isChecked(),
                )
                msg = ngettext("PDF saved ({pages} page).", "PDF saved ({pages} pages).", pages).format(pages=pages)
            else:
                export_png(
                    path,
                    self.doc.view,
                    self.doc.layout,
                    scale,
                    top,
                    base,
                    dpi=self.dpi.value(),
                    heading=self.heading.isChecked(),
                )
                msg = _("Image saved.")
        except (ExportError, OSError) as e:
            QMessageBox.warning(self, _("Export"), _("Could not export: {error}").format(error=e))
            return
        QMessageBox.information(self, _("Export"), msg)
        self.accept()
