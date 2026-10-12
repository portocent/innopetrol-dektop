"""Ventana principal: menús, barra de herramientas, área MDI y árbol de pozos."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QComboBox, QDockWidget, QFileDialog, QLabel, QMainWindow, QMdiArea,
                               QMessageBox, QToolBar)

from innopetrol import __version__
from innopetrol.model.layout import LogLayout
from innopetrol.model.mnemonics import build_triple_combo
from innopetrol.model.project import SUFFIX as PROJECT_SUFFIX
from innopetrol.model.project import ProjectError, WellEntry, load_project, save_project
from innopetrol.model.scales import SCALE_PRESETS
from innopetrol.model.template import SUFFIX as TEMPLATE_SUFFIX
from innopetrol.model.template import (TemplateError, apply_template, load_template, save_template,
                                       template_from_json, template_to_json)
from innopetrol.model.well import Well
from innopetrol.resources import app_icon
from innopetrol.ui.document import WellDocument
from innopetrol.ui.well_tree import WellTree
from innopetrol.ui.well_view import WellView

LAS_FILTER = "Archivos LAS (*.las *.LAS);;Todos los archivos (*)"
PROJECT_FILTER = f"Proyecto InnoPetrol (*{PROJECT_SUFFIX})"
TEMPLATE_FILTER = f"Plantilla InnoPetrol (*{TEMPLATE_SUFFIX} *.json)"
MAX_RECENT = 8


class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings | None = None):
        super().__init__()
        self.settings = settings or QSettings("InnoPetrol", "Visor de Pozos")
        self.setWindowTitle("InnoPetrol — Visor de Pozos")
        self.setWindowIcon(app_icon())
        self.resize(1400, 900)
        self.setAcceptDrops(True)

        self.docs: list[WellDocument] = []
        self.views: dict[WellDocument, WellView] = {}
        self.project_path: Path | None = None
        self.dirty = False
        self._windows = []  # ventanas no modales abiertas (evita que el recolector las cierre)

        self.mdi = QMdiArea()
        self.mdi.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.mdi.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.mdi.subWindowActivated.connect(self._active_changed)
        self.setCentralWidget(self.mdi)

        self.tree = WellTree()
        dock = QDockWidget("Pozos", self)
        dock.setObjectName("dock_pozos")
        dock.setWidget(self.tree)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        self.tree.docActivated.connect(self.activate_doc)
        self.tree.curveStatsRequested.connect(self.show_stats)
        self.tree.curveDeleteRequested.connect(self._delete_curve)
        self.tree.topsRequested.connect(self.edit_tops)
        self.tree.topActivated.connect(self._go_to_top)
        self.tree.set_template_name(self.settings.value("default_template_name"))

        self.scale_label = QLabel()
        self.statusBar().addPermanentWidget(self.scale_label)
        self.statusBar().showMessage("Listo. Abra un archivo LAS (Ctrl+O) o arrástrelo a la ventana.")
        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._update_actions()
        geo = self.settings.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)

    # ================================================================== acciones y menús

    def _action(self, text, slot, shortcut=None, tip=None, needs_doc=True) -> QAction:
        a = QAction(text, self)
        a.triggered.connect(lambda checked=False: slot())
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        if tip:
            a.setStatusTip(tip)
        a.setProperty("needs_doc", needs_doc)
        return a

    def _build_actions(self):
        A = self._action
        self.a_open = A("Abrir LAS…", self.open_las_dialog, QKeySequence.Open, "Abrir uno o más archivos LAS", False)
        self.a_open_proj = A("Abrir proyecto…", self.open_project_dialog, "Ctrl+Shift+O", needs_doc=False)
        self.a_save_proj = A("Guardar proyecto", self.save_project, QKeySequence.Save)
        self.a_save_proj_as = A("Guardar proyecto como…", lambda: self.save_project(ask=True), "Ctrl+Shift+S")
        self.a_export = A("Exportar registro (PDF / PNG)…", self.export_log, "Ctrl+E")
        self.a_export_las = A("Exportar LAS (con curvas calculadas)…", self.export_las)
        self.a_export_csv = A("Exportar CSV…", self.export_csv)
        self.a_quit = A("Salir", self.close, QKeySequence.Quit, needs_doc=False)

        self.a_tpl_save = A("Guardar plantilla del pozo activo…", self.save_template, "Ctrl+T")
        self.a_tpl_load = A("Cargar plantilla y aplicar al pozo activo…", self.load_template, "Ctrl+L")
        self.a_tpl_all = A("Aplicar layout del pozo activo a todos los pozos", self.apply_to_all)
        self.a_tpl_default = A("Usar layout del pozo activo como plantilla por defecto", self.set_default_template)
        self.a_tpl_reset = A("Restablecer plantilla por defecto (Triple Combo)", self.reset_default_template,
                             needs_doc=False)
        self.a_tpl_triple = A("Reconstruir Triple Combo en el pozo activo", self.rebuild_triple_combo)

        self.a_add_track = A("Agregar track", lambda: self._view_call("add_track"), "Ctrl+Shift+T")
        self.a_edit_track = A("Editar track seleccionado…", lambda: self._view_call("edit_track"), "Ctrl+Shift+E")
        self.a_del_track = A("Eliminar track seleccionado", lambda: self._view_call("remove_track"))
        self.a_tops = A("Topes de formación…", lambda: self.edit_tops(self.active_doc()), "Ctrl+Shift+F")
        self.a_petro = A("Petrofísica básica (Vsh, φ, Sw)…", self.petrophysics, "Ctrl+P")
        self.a_calc = A("Calculadora de curvas…", self.calculator, "Ctrl+K")
        self.a_zones = A("Resumen por zonas (net pay)…", self.zone_summary)
        self.a_stats = A("Estadísticas e histograma…", lambda: self.show_stats(self.active_doc()))
        self.a_table = A("Tabla de datos", self.data_table, "Ctrl+D")

        self.a_xplot = A("Crossplot…", lambda: self.crossplot("free"), "Ctrl+X")
        self.a_nd = A("Crossplot Neutrón-Densidad…", lambda: self.crossplot("nd"))
        self.a_pickett = A("Gráfico de Pickett…", lambda: self.crossplot("pickett"))
        self.a_corr = A("Correlación de pozos…", self.correlation, "Ctrl+R")
        self.a_fit = A("Ajustar a la ventana", lambda: self._view_call_canvas("fit"), "Ctrl+0")
        self.a_tile = A("Mosaico", self.mdi.tileSubWindows, needs_doc=False)
        self.a_cascade = A("Cascada", self.mdi.cascadeSubWindows, needs_doc=False)
        self.a_tabs = A("Ver como pestañas", self._toggle_tabs, needs_doc=False)
        self.a_tabs.setCheckable(True)

        self.a_help = A("Navegación y atajos", self.show_help, "F1", needs_doc=False)
        self.a_about = A("Acerca de InnoPetrol", self.show_about, needs_doc=False)

    def _build_menus(self):
        mb = self.menuBar()
        m = mb.addMenu("&Archivo")
        m.addAction(self.a_open)
        self.recent_menu = m.addMenu("Abrir reciente")
        self._refresh_recent()
        m.addSeparator()
        for a in (self.a_open_proj, self.a_save_proj, self.a_save_proj_as):
            m.addAction(a)
        m.addSeparator()
        for a in (self.a_export, self.a_export_las, self.a_export_csv):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.a_quit)

        m = mb.addMenu("&Plantilla")
        for a in (self.a_tpl_save, self.a_tpl_load, None, self.a_tpl_all, self.a_tpl_default, self.a_tpl_reset,
                  None, self.a_tpl_triple):
            m.addSeparator() if a is None else m.addAction(a)

        m = mb.addMenu("P&ozo")
        for a in (self.a_add_track, self.a_edit_track, self.a_del_track, None, self.a_tops, None, self.a_petro,
                  self.a_calc, self.a_zones, None, self.a_stats, self.a_table):
            m.addSeparator() if a is None else m.addAction(a)

        m = mb.addMenu("&Análisis")
        for a in (self.a_xplot, self.a_nd, self.a_pickett, None, self.a_corr):
            m.addSeparator() if a is None else m.addAction(a)

        m = mb.addMenu("&Ver")
        m.addAction(self.a_fit)
        self.scale_menu = m.addMenu("Escala vertical")
        for n in SCALE_PRESETS:
            self.scale_menu.addAction(f"1:{n}").triggered.connect(lambda _=False, n=n: self._set_scale(n))
        m.addSeparator()
        for a in (self.a_tile, self.a_cascade, self.a_tabs):
            m.addAction(a)

        m = mb.addMenu("A&yuda")
        m.addAction(self.a_help)
        m.addAction(self.a_about)

    def _build_toolbar(self):
        tb = QToolBar("Principal")
        tb.setObjectName("toolbar_principal")
        tb.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.addToolBar(tb)
        tb.addAction(self.a_open)
        tb.addAction(self.a_save_proj)
        tb.addSeparator()
        tb.addWidget(QLabel(" Escala "))
        self.scale_combo = QComboBox()
        self.scale_combo.setEditable(True)
        self.scale_combo.setMinimumWidth(110)
        self.scale_combo.addItem("Ajustar")
        for n in SCALE_PRESETS:
            self.scale_combo.addItem(f"1:{n}")
        self.scale_combo.activated.connect(lambda _: self._scale_from_combo())
        self.scale_combo.lineEdit().returnPressed.connect(self._scale_from_combo)
        tb.addWidget(self.scale_combo)
        tb.addSeparator()
        for a in (self.a_add_track, self.a_tops, self.a_petro, self.a_calc, self.a_zones):
            tb.addAction(a)
        tb.addSeparator()
        for a in (self.a_xplot, self.a_corr, self.a_table, self.a_export):
            tb.addAction(a)
        self.a_add_track.setIconText("+ Track")
        self.a_tops.setIconText("Topes")
        self.a_petro.setIconText("Petrofísica")
        self.a_calc.setIconText("Calculadora")
        self.a_zones.setIconText("Zonas")
        self.a_xplot.setIconText("Crossplot")
        self.a_corr.setIconText("Correlación")
        self.a_table.setIconText("Datos")
        self.a_export.setIconText("Exportar")
        self.a_open.setIconText("Abrir LAS")
        self.a_save_proj.setIconText("Guardar")

    def _update_actions(self):
        has = bool(self.docs)
        for a in self.findChildren(QAction):
            if a.property("needs_doc"):
                a.setEnabled(has)
        self.a_corr.setEnabled(len(self.docs) >= 2)
        self.scale_combo.setEnabled(has)

    # ================================================================== pozo activo

    def active_view(self) -> WellView | None:
        sub = self.mdi.activeSubWindow() or self.mdi.currentSubWindow()
        if sub is not None and isinstance(sub.widget(), WellView):
            return sub.widget()
        return self.views.get(self.docs[0]) if len(self.docs) == 1 else None

    def active_doc(self) -> WellDocument | None:
        v = self.active_view()
        if v is None and self.docs:
            self.statusBar().showMessage("Seleccione la ventana de un pozo.", 4000)
        return v.doc if v else None

    def _view_call(self, method: str):
        v = self.active_view()
        if v:
            getattr(v, method)()

    def _view_call_canvas(self, method: str):
        v = self.active_view()
        if v:
            getattr(v.canvas, method)()

    def _active_changed(self, sub):
        v = sub.widget() if sub else None
        if isinstance(v, WellView):
            self.tree.select_doc(v.doc)
            self._show_scale(v)

    def activate_doc(self, doc):
        v = self.views.get(doc)
        if v:
            self.mdi.setActiveSubWindow(v.parentWidget())
            if v.parentWidget().isMinimized():
                v.parentWidget().showNormal()
            v.canvas.setFocus()

    def _go_to_top(self, doc, depth: float):
        self.activate_doc(doc)
        v = self.views.get(doc)
        if v:
            v.canvas.center_on(depth)

    def _show_scale(self, v: WellView):
        if v is not self.active_view():
            return
        text = "Ajustar" if v.canvas.fit_mode else f"1:{v.canvas.current_scale():.0f}"
        self.scale_combo.blockSignals(True)
        self.scale_combo.setEditText(text)
        self.scale_combo.blockSignals(False)
        lo, hi = v.canvas.visible_depth_range()
        self.scale_label.setText(f"{v.doc.title} · escala 1:{v.canvas.current_scale():.0f} · "
                                 f"visible {max(lo, v.doc.well.start):.1f} – {min(hi, v.doc.well.stop):.1f} "
                                 f"{v.doc.well.depth_unit}")

    def _scale_from_combo(self):
        text = self.scale_combo.currentText().strip().lower()
        v = self.active_view()
        if not v:
            return
        if text.startswith("aj") or text == "fit":
            v.canvas.fit()
            return
        try:
            n = float(text.split(":")[-1].replace(",", "."))
            if n <= 0:
                raise ValueError
        except ValueError:
            self.statusBar().showMessage("Escriba la escala como 1:500 o 500.", 4000)
            return
        v.canvas.set_scale(n)

    def _set_scale(self, n):
        v = self.active_view()
        if v:
            v.canvas.set_scale(n)

    # ================================================================== abrir pozos

    def open_las_dialog(self):
        start = self.settings.value("last_dir", str(Path.home()))
        paths, _ = QFileDialog.getOpenFileNames(self, "Abrir archivos LAS", start, LAS_FILTER)
        if paths:
            self.settings.setValue("last_dir", str(Path(paths[0]).parent))
            self.open_las(paths)

    def open_las(self, paths):
        errors, opened = [], []
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for path in paths:
                try:
                    well = Well.from_las(path)
                except Exception as e:  # noqa: BLE001 - se informa cualquier archivo inválido
                    errors.append(f"{Path(path).name}: {e}")
                    continue
                layout, missing = self._default_layout(well)
                doc = self.add_doc(well, layout)
                opened.append(doc.title)
                self._add_recent(path)
                if missing:
                    self.statusBar().showMessage(
                        f"{doc.title}: la plantilla por defecto usa curvas que no están en el pozo: {', '.join(missing)}",
                        8000)
        finally:
            QApplication.restoreOverrideCursor()
        if errors:
            QMessageBox.warning(self, "Abrir LAS", "No se pudieron abrir:\n\n" + "\n".join(errors))
        if opened and not errors:
            self.statusBar().showMessage(f"Cargado: {', '.join(opened)}", 5000)

    def _default_layout(self, well) -> tuple[LogLayout, list[str]]:
        text = self.settings.value("default_template_json")
        if text:
            try:
                layout, missing = apply_template(template_from_json(text), well)
                if any(t.curves for t in layout.tracks):
                    return layout, missing
            except TemplateError:
                pass
        return build_triple_combo(well), []

    def add_doc(self, well, layout, petro=None) -> WellDocument:
        doc = WellDocument(well, layout, petro, self)
        view = WellView(doc)
        sub = self.mdi.addSubWindow(view)
        sub.setWindowIcon(app_icon())
        sub.resize(min(int(sum(t.width for t in layout.tracks)) + 40, max(self.mdi.width() - 20, 400)),
                   max(self.mdi.height() - 20, 400))
        view.statusMessage.connect(lambda msg: self.statusBar().showMessage(msg))
        view.exportRequested.connect(self.export_log)
        view.closed.connect(self._doc_closed)
        view.canvas.viewChanged.connect(lambda v=view: self._show_scale(v))
        for sig in (doc.layoutChanged, doc.curvesChanged, doc.topsChanged):
            sig.connect(self._mark_dirty)
        self.docs.append(doc)
        self.views[doc] = view
        self.tree.add_doc(doc)
        sub.show()
        self._update_actions()
        self.dirty = True
        return doc

    def _doc_closed(self, doc):
        if doc in self.docs:
            self.docs.remove(doc)
            self.views.pop(doc, None)
            self.tree.remove_doc(doc)
            self._update_actions()

    def _mark_dirty(self):
        self.dirty = True

    def _add_recent(self, path):
        recent = [p for p in (self.settings.value("recent") or []) if p != str(path)]
        recent.insert(0, str(path))
        self.settings.setValue("recent", recent[:MAX_RECENT])
        self._refresh_recent()

    def _refresh_recent(self):
        self.recent_menu.clear()
        recent = self.settings.value("recent") or []
        if isinstance(recent, str):
            recent = [recent]
        for p in recent:
            a = self.recent_menu.addAction(Path(p).name)
            a.setStatusTip(p)
            if p.endswith(PROJECT_SUFFIX):
                a.triggered.connect(lambda _=False, p=p: self.open_project(p))
            else:
                a.triggered.connect(lambda _=False, p=p: self.open_las([p]))
        self.recent_menu.setEnabled(bool(recent))

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        projects = [p for p in paths if p.endswith(PROJECT_SUFFIX)]
        if projects:
            self.open_project(projects[0])
        las = [p for p in paths if p.lower().endswith(".las")]
        if las:
            self.open_las(las)

    # ================================================================== proyecto

    def open_project_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir proyecto", self.settings.value("last_dir", ""),
                                              PROJECT_FILTER)
        if path:
            self.open_project(path)

    def open_project(self, path):
        if self.docs and not self._confirm_discard():
            return
        try:
            result = load_project(path)
        except ProjectError as e:
            QMessageBox.warning(self, "Abrir proyecto", str(e))
            return
        self._close_all()
        for entry in result.entries:
            self.add_doc(entry.well, entry.layout, entry.petro)
        self.project_path = Path(path)
        self.dirty = False
        self._add_recent(path)
        self._update_title()
        if result.errors:
            QMessageBox.warning(self, "Abrir proyecto", "Algunos elementos no se pudieron cargar:\n\n"
                                + "\n".join(result.errors))

    def save_project(self, ask: bool = False) -> bool:
        if not self.docs:
            return False
        path = self.project_path
        if ask or path is None:
            name, _ = QFileDialog.getSaveFileName(self, "Guardar proyecto", str(path or Path.home() / f"proyecto{PROJECT_SUFFIX}"),
                                                  PROJECT_FILTER)
            if not name:
                return False
            path = Path(name if name.endswith(PROJECT_SUFFIX) else name + PROJECT_SUFFIX)
        try:
            save_project(path, [WellEntry(d.well, d.layout, d.petro) for d in self.docs])
        except OSError as e:
            QMessageBox.warning(self, "Guardar proyecto", f"No se pudo guardar: {e}")
            return False
        self.project_path = path
        self.dirty = False
        self._add_recent(str(path))
        self._update_title()
        self.statusBar().showMessage(f"Proyecto guardado en {path}", 5000)
        return True

    def _update_title(self):
        name = f" — {self.project_path.name}" if self.project_path else ""
        self.setWindowTitle(f"InnoPetrol — Visor de Pozos{name}")

    def _close_all(self):
        for v in list(self.views.values()):
            v.confirm_close = False
            v.parentWidget().close()

    def _confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        r = QMessageBox.question(self, "Cambios sin guardar", "¿Guardar el proyecto actual antes de continuar?",
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if r == QMessageBox.Save:
            return self.save_project()
        return r == QMessageBox.Discard

    def closeEvent(self, e):
        if self.docs and not self._confirm_discard():
            e.ignore()
            return
        self.settings.setValue("geometry", self.saveGeometry())
        self._close_all()
        e.accept()

    # ================================================================== plantillas

    def save_template(self):
        doc = self.active_doc()
        if not doc:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Guardar plantilla", f"plantilla{TEMPLATE_SUFFIX}",
                                              TEMPLATE_FILTER)
        if path:
            if not path.endswith(".json"):
                path += TEMPLATE_SUFFIX
            save_template(path, doc.layout)
            self.statusBar().showMessage(f"Plantilla guardada: {path}", 5000)

    def load_template(self):
        doc = self.active_doc()
        if not doc:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Cargar plantilla", "", TEMPLATE_FILTER)
        if not path:
            return
        try:
            layout = load_template(path)
        except (TemplateError, OSError) as e:
            QMessageBox.warning(self, "Cargar plantilla", str(e))
            return
        self._apply_layout(doc, layout)

    def _apply_layout(self, doc, layout) -> list[str]:
        result, missing = apply_template(layout, doc.well)
        doc.set_layout(result)
        if missing:
            self.statusBar().showMessage(f"{doc.title}: curvas no encontradas: {', '.join(missing)}", 8000)
        return missing

    def apply_to_all(self):
        doc = self.active_doc()
        if not doc:
            return
        report = []
        for other in self.docs:
            if other is not doc:
                missing = self._apply_layout(other, doc.layout)
                if missing:
                    report.append(f"{other.title}: faltan {', '.join(missing)}")
        QMessageBox.information(self, "Aplicar a todos", "Layout aplicado." + ("\n\n" + "\n".join(report) if report else ""))

    def set_default_template(self):
        doc = self.active_doc()
        if not doc:
            return
        self.settings.setValue("default_template_json", template_to_json(doc.layout))
        self.settings.setValue("default_template_name", f"layout de {doc.title}")
        self.tree.set_template_name(f"layout de {doc.title}")
        self.statusBar().showMessage("Plantilla por defecto actualizada: se usará al abrir nuevos pozos.", 5000)

    def reset_default_template(self):
        self.settings.remove("default_template_json")
        self.settings.remove("default_template_name")
        self.tree.set_template_name(None)

    def rebuild_triple_combo(self):
        doc = self.active_doc()
        if doc:
            doc.set_layout(build_triple_combo(doc.well))

    # ================================================================== herramientas

    def edit_tops(self, doc):
        if doc:
            from innopetrol.ui.tops_dialog import TopsDialog

            TopsDialog(doc, self).exec()

    def petrophysics(self):
        doc = self.active_doc()
        if doc:
            from innopetrol.ui.petro_dialog import PetroDialog

            PetroDialog(doc, self).exec()

    def calculator(self):
        doc = self.active_doc()
        if doc:
            from innopetrol.ui.petro_dialog import CalculatorDialog

            CalculatorDialog(doc, self).exec()

    def zone_summary(self):
        doc = self.active_doc()
        if doc:
            from innopetrol.ui.petro_dialog import ZoneSummaryDialog

            ZoneSummaryDialog(doc, self).exec()

    def show_stats(self, doc, curve: str | None = None):
        if doc:
            from innopetrol.ui.analysis import StatsDialog

            self._modeless(StatsDialog(doc, curve, self))

    def data_table(self):
        doc = self.active_doc()
        if doc:
            from innopetrol.ui.analysis import DataTableWindow

            self._modeless(DataTableWindow(doc, self))

    def crossplot(self, mode: str):
        doc = self.active_doc()
        if doc:
            from innopetrol.ui.crossplot import CrossplotWindow

            self._modeless(CrossplotWindow(doc, mode, self))

    def correlation(self):
        from innopetrol.ui.correlation import CorrelationSetup, CorrelationWindow

        if len(self.docs) < 2:
            QMessageBox.information(self, "Correlación", "Abra al menos dos pozos.")
            return
        setup = CorrelationSetup(self.docs, self)
        if setup.exec():
            docs = setup.selected()
            if len(docs) < 1:
                return
            self._modeless(CorrelationWindow(docs, setup.datum.currentData(), self, setup.tracks.currentData()))

    def _modeless(self, w):
        w.setAttribute(Qt.WA_DeleteOnClose)
        self._windows.append(w)
        w.destroyed.connect(lambda _=None, w=w: self._windows.remove(w) if w in self._windows else None)
        w.show()

    def _delete_curve(self, doc, name):
        r = QMessageBox.question(self, "Eliminar curva", f"¿Eliminar la curva calculada {name}?")
        if r == QMessageBox.Yes:
            doc.remove_curve(name)

    def export_log(self):
        v = self.active_view()
        if not v:
            return
        from innopetrol.ui.export_dialog import ExportDialog

        ExportDialog(v.doc, v.canvas.visible_depth_range(), v.canvas.current_scale(), self).exec()

    def export_las(self):
        doc = self.active_doc()
        if not doc:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar LAS", f"{doc.title}.las", "LAS (*.las)")
        if path:
            try:
                doc.well.to_las(path)
                self.statusBar().showMessage(f"LAS exportado: {path}", 5000)
            except Exception as e:  # noqa: BLE001
                QMessageBox.warning(self, "Exportar LAS", f"No se pudo exportar: {e}")

    def export_csv(self):
        doc = self.active_doc()
        if not doc:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar CSV", f"{doc.title}.csv", "CSV (*.csv)")
        if path:
            try:
                doc.well.to_csv(path)
                self.statusBar().showMessage(f"CSV exportado: {path}", 5000)
            except OSError as e:
                QMessageBox.warning(self, "Exportar CSV", f"No se pudo exportar: {e}")

    def _toggle_tabs(self):
        self.mdi.setViewMode(QMdiArea.TabbedView if self.a_tabs.isChecked() else QMdiArea.SubWindowView)
        self.mdi.setTabsClosable(True)
        self.mdi.setTabsMovable(True)

    # ================================================================== ayuda

    def show_help(self):
        QMessageBox.information(self, "Navegación y atajos", """<b>Registro</b><br>
Rueda: desplazar en profundidad · Ctrl + rueda: zoom en el cursor · Shift + rueda: desplazar horizontal<br>
RePág/AvPág, Inicio/Fin, flechas, + / − · Ctrl+0: ajustar a la ventana<br>
Arrastrar el borde de un track: cambiar su ancho · Doble clic en un track: editarlo<br>
Clic derecho: menú del track (agregar, mover, eliminar, agregar tope, escala, exportar)<br><br>
<b>Árbol de pozos</b><br>
Doble clic en una curva: estadísticas e histograma · Doble clic en un tope: ir a esa profundidad<br><br>
<b>Atajos</b><br>
Ctrl+O abrir LAS · Ctrl+S guardar proyecto · Ctrl+E exportar · Ctrl+T / Ctrl+L guardar / cargar plantilla<br>
Ctrl+Shift+T agregar track · Ctrl+Shift+F topes · Ctrl+P petrofísica · Ctrl+K calculadora<br>
Ctrl+X crossplot · Ctrl+R correlación · Ctrl+D tabla de datos""")

    def show_about(self):
        QMessageBox.about(self, "Acerca de InnoPetrol", f"""<h3>InnoPetrol — Visor de Pozos {__version__}</h3>
<p>Visualización de registros de pozo en formato LAS para ingenieros de petróleo:
tracks configurables, escalas lineales y logarítmicas, rellenos, topes, petrofísica básica,
crossplots, correlación entre pozos y exportación a PDF/PNG/LAS.</p>
<p>Proyecto original 2020 · reescrito con Python {'.'.join(map(str, __import__('sys').version_info[:2]))} y PySide6.</p>""")

