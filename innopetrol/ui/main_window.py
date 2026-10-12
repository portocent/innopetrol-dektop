"""Main window: menus, toolbar, MDI area and the well tree.

Widgets are created once in ``_build_*`` and every visible text is set in ``retranslate()``, so
the interface language can be switched at runtime without recreating the window.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QUndoGroup
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMdiArea,
    QMessageBox,
    QToolBar,
    QWidget,
)

from innopetrol import i18n
from innopetrol.i18n import _
from innopetrol.model import units
from innopetrol.model.io import is_well_file, load_wells
from innopetrol.model.layout import LogLayout
from innopetrol.model.mnemonics import build_triple_combo
from innopetrol.model.project import SUFFIX as PROJECT_SUFFIX
from innopetrol.model.project import ProjectError, load_project
from innopetrol.model.scales import SCALE_PRESETS
from innopetrol.model.template import SUFFIX as TEMPLATE_SUFFIX
from innopetrol.model.template import (
    TemplateError,
    apply_template,
    load_template,
    save_template,
    template_from_json,
    template_to_json,
)
from innopetrol.resources import app_icon
from innopetrol.ui.document import WellDocument
from innopetrol.ui.help_dialogs import show_about, show_help
from innopetrol.ui.session import Session
from innopetrol.ui.well_tree import WellTree
from innopetrol.ui.well_view import WellView
from innopetrol.ui.widgets import key_text

AUTOSAVE_MS = 2 * 60 * 1000  # autosave interval while there are unsaved changes
# QSettings identifiers. They are storage keys, not interface text: changing them would lose
# existing users' settings (recent files, default template, language).
SETTINGS_ORG, SETTINGS_APP = "InnoPetrol", "Visor de Pozos"


class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings | None = None):
        super().__init__()
        self.settings = settings or QSettings(SETTINGS_ORG, SETTINGS_APP)
        self.setWindowIcon(app_icon())
        self.resize(1400, 900)
        self.setAcceptDrops(True)

        self._load_aliases()
        language = self.settings.value("language") or i18n.system_language()
        i18n.set_language(language)
        app = QApplication.instance()
        if app is not None:
            i18n.install_qt_translator(app, i18n.current_language())

        self.docs: list[WellDocument] = []
        self.views: dict[WellDocument, WellView] = {}
        self.session = Session(self.settings)
        self._windows: list[QWidget] = []  # open non-modal windows (keeps them from being garbage collected)
        # One undo history per well; the group follows the active well window.
        self.undo_group = QUndoGroup(self)
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(AUTOSAVE_MS)
        self.autosave_timer.timeout.connect(self.autosave)
        self.autosave_timer.start()

        self.mdi = QMdiArea()
        self.mdi.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.mdi.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.mdi.subWindowActivated.connect(self._active_changed)
        self.setCentralWidget(self.mdi)

        self.tree = WellTree()
        self.dock = QDockWidget(self)
        self.dock.setObjectName("dock_wells")
        self.dock.setWidget(self.tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock)
        self.tree.docActivated.connect(self.activate_doc)
        self.tree.curveStatsRequested.connect(self.show_stats)
        self.tree.curveEditRequested.connect(self.curve_tools)
        self.tree.curveDeleteRequested.connect(self._delete_curve)
        self.tree.curveUnitRequested.connect(self.set_curve_unit)
        self.tree.topsRequested.connect(self.edit_tops)
        self.tree.intervalsRequested.connect(self.edit_intervals)
        self.tree.topActivated.connect(self._go_to_top)
        self.tree.set_template_name(self.settings.value("default_template_name"))

        self.scale_label = QLabel()
        self.statusBar().addPermanentWidget(self.scale_label)
        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self.retranslate()
        self._update_actions()
        geo = self.settings.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)

    # ================================================================== actions and menus

    def _action(self, slot, shortcut=None, needs_doc=True) -> QAction:
        a = QAction(self)
        a.triggered.connect(lambda checked=False: slot())
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.setProperty("needs_doc", needs_doc)
        return a

    def _build_actions(self):
        A = self._action
        self.a_open = A(self.open_las_dialog, QKeySequence.StandardKey.Open, needs_doc=False)
        self.a_open_proj = A(self.open_project_dialog, "Ctrl+Shift+O", needs_doc=False)
        self.a_save_proj = A(self.save_project, QKeySequence.StandardKey.Save)
        self.a_save_proj_as = A(lambda: self.save_project(ask=True), "Ctrl+Shift+S")
        self.a_export = A(self.export_log, "Ctrl+E")
        self.a_export_las = A(self.export_las)
        self.a_export_csv = A(self.export_csv)
        self.a_quit = A(self.close, QKeySequence.StandardKey.Quit, needs_doc=False)
        self._build_undo_actions()

        self.a_tpl_save = A(self.save_template, "Ctrl+T")
        self.a_tpl_load = A(self.load_template, "Ctrl+L")
        self.a_tpl_all = A(self.apply_to_all)
        self.a_tpl_default = A(self.set_default_template)
        self.a_tpl_reset = A(self.reset_default_template, needs_doc=False)
        self.a_tpl_triple = A(self.rebuild_triple_combo)
        self.a_aliases = A(self.edit_aliases, needs_doc=False)

        self.a_add_track = A(lambda: self._view_call("add_track"), "Ctrl+Shift+T")
        self.a_edit_track = A(lambda: self._view_call("edit_track"), "Ctrl+Shift+E")
        self.a_del_track = A(lambda: self._view_call("remove_track"))
        self.a_tops = A(lambda: self.edit_tops(self.active_doc()), "Ctrl+Shift+F")
        self.a_survey = A(self.edit_survey)
        self.a_intervals = A(lambda: self.edit_intervals(self.active_doc()))
        self.a_core = A(self.import_core)
        # Depth reference (MD/TVD/TVDSS) and display unit of the active well; unit system of all wells.
        self.reference_actions = self._choice_actions(("md", "tvd", "tvdss"), self.set_depth_reference, needs_doc=True)
        self.unit_actions = self._choice_actions(
            ("file", "m", "ft"), lambda code: self.set_display_unit(None if code == "file" else code), needs_doc=True
        )
        self.system_actions = self._choice_actions(units.SYSTEMS, self.set_unit_system)
        self.a_petro = A(self.petrophysics, "Ctrl+P")
        self.a_calc = A(self.calculator, "Ctrl+K")
        self.a_curve_tools = A(lambda: self.curve_tools(self.active_doc()))
        self.a_normalize = A(self.normalize_curves)
        self.a_zones = A(self.zone_summary)
        self.a_stats = A(lambda: self.show_stats(self.active_doc()))
        self.a_table = A(self.data_table, "Ctrl+D")

        self.a_xplot = A(lambda: self.crossplot("free"), "Ctrl+X")
        self.a_nd = A(lambda: self.crossplot("nd"))
        self.a_pickett = A(lambda: self.crossplot("pickett"))
        self.a_corr = A(self.correlation, "Ctrl+R")
        self.a_map = A(self.base_map, "Ctrl+Shift+M")  # ⌘M minimizes on Mac
        self.a_fit = A(lambda: self._view_call_canvas("fit"), "Ctrl+0")
        self.a_zoom_in = A(lambda: self._zoom_step(1), QKeySequence.StandardKey.ZoomIn)
        self.a_zoom_out = A(lambda: self._zoom_step(-1), QKeySequence.StandardKey.ZoomOut)
        # Ctrl+= as well as Ctrl++: on many keyboards "+" needs Shift.
        self.a_zoom_in.setShortcuts([QKeySequence(QKeySequence.StandardKey.ZoomIn), QKeySequence("Ctrl+=")])
        self.a_tile = A(self.mdi.tileSubWindows, needs_doc=False)
        self.a_cascade = A(self.mdi.cascadeSubWindows, needs_doc=False)
        self.a_tabs = A(self._toggle_tabs, needs_doc=False)
        self.a_tabs.setCheckable(True)

        # Language names are shown in their own language so anyone can find theirs.
        self.language_actions = self._choice_actions(i18n.LANGUAGES, self.set_language)
        for code, name in i18n.LANGUAGES.items():
            self.language_actions[code].setText(name)

        self.a_help = A(lambda: show_help(self), "F1", needs_doc=False)
        self.a_about = A(lambda: show_about(self), needs_doc=False)
        self.a_equations = A(self.show_equations, needs_doc=False)

    def _build_undo_actions(self):
        self.a_undo = self._action(self.undo_group.undo, QKeySequence.StandardKey.Undo, needs_doc=False)
        self.a_redo = self._action(self.undo_group.redo, QKeySequence.StandardKey.Redo, needs_doc=False)
        # Ctrl+Y as well: the usual redo shortcut on Windows besides Ctrl+Shift+Z.
        self.a_redo.setShortcuts([QKeySequence(QKeySequence.StandardKey.Redo), QKeySequence("Ctrl+Y")])
        self.a_undo.setEnabled(False)
        self.a_redo.setEnabled(False)
        self.undo_group.canUndoChanged.connect(self.a_undo.setEnabled)
        self.undo_group.canRedoChanged.connect(self.a_redo.setEnabled)
        self.undo_group.undoTextChanged.connect(lambda _text: self._undo_texts())
        self.undo_group.redoTextChanged.connect(lambda _text: self._undo_texts())

    def _choice_actions(self, codes, slot, needs_doc: bool = False) -> dict[str, QAction]:
        """Mutually exclusive checkable actions, one per code; triggering one calls slot(code).
        Their texts are set in retranslate()."""
        group = QActionGroup(self)
        actions = {}
        for code in codes:
            a = QAction(self, checkable=True)
            a.setProperty("needs_doc", needs_doc)
            a.triggered.connect(lambda _checked=False, code=code: slot(code))
            group.addAction(a)
            actions[code] = a
        return actions

    def _build_menus(self):
        mb = self.menuBar()
        self.m_file = mb.addMenu("")
        self.m_file.addAction(self.a_open)
        self.recent_menu = self.m_file.addMenu("")
        self.m_file.addSeparator()
        for a in (self.a_open_proj, self.a_save_proj, self.a_save_proj_as):
            self.m_file.addAction(a)
        self.m_file.addSeparator()
        for a in (self.a_export, self.a_export_las, self.a_export_csv):
            self.m_file.addAction(a)
        self.m_file.addSeparator()
        self.m_file.addAction(self.a_quit)

        self.m_edit = mb.addMenu("")
        self.m_edit.addAction(self.a_undo)
        self.m_edit.addAction(self.a_redo)

        self.m_template = mb.addMenu("")
        for a in (
            self.a_tpl_save,
            self.a_tpl_load,
            None,
            self.a_tpl_all,
            self.a_tpl_default,
            self.a_tpl_reset,
            None,
            self.a_tpl_triple,
            None,
            self.a_aliases,
        ):
            self.m_template.addSeparator() if a is None else self.m_template.addAction(a)

        self.m_well = mb.addMenu("")
        for a in (
            self.a_add_track,
            self.a_edit_track,
            self.a_del_track,
            None,
            self.a_tops,
            self.a_survey,
            self.a_intervals,
            self.a_core,
            None,
            self.a_petro,
            self.a_calc,
            self.a_curve_tools,
            self.a_zones,
            None,
            self.a_stats,
            self.a_table,
        ):
            self.m_well.addSeparator() if a is None else self.m_well.addAction(a)

        self.m_analysis = mb.addMenu("")
        for a in (self.a_xplot, self.a_nd, self.a_pickett, None, self.a_corr, self.a_map, None, self.a_normalize):
            self.m_analysis.addSeparator() if a is None else self.m_analysis.addAction(a)

        self.m_view = mb.addMenu("")
        self.m_view.addAction(self.a_zoom_in)
        self.m_view.addAction(self.a_zoom_out)
        self.m_view.addAction(self.a_fit)
        self.scale_menu = self.m_view.addMenu("")
        for n in SCALE_PRESETS:
            self.scale_menu.addAction(f"1:{n}").triggered.connect(lambda _checked=False, n=n: self._set_scale(n))
        self.reference_menu = self.m_view.addMenu("")
        for a in self.reference_actions.values():
            self.reference_menu.addAction(a)
        self.unit_menu = self.m_view.addMenu("")
        for a in self.unit_actions.values():
            self.unit_menu.addAction(a)
        self.system_menu = self.m_view.addMenu("")
        for a in self.system_actions.values():
            self.system_menu.addAction(a)
        self.m_view.addSeparator()
        for a in (self.a_tile, self.a_cascade, self.a_tabs):
            self.m_view.addAction(a)
        self.m_view.addSeparator()
        self.language_menu = self.m_view.addMenu("")
        for a in self.language_actions.values():
            self.language_menu.addAction(a)

        self.m_help = mb.addMenu("")
        self.m_help.addAction(self.a_help)
        self.m_help.addAction(self.a_equations)
        self.m_help.addAction(self.a_about)

    def _build_toolbar(self):
        self.toolbar = tb = QToolBar(self)
        tb.setObjectName("toolbar_main")
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(tb)
        tb.addAction(self.a_open)
        tb.addAction(self.a_save_proj)
        tb.addAction(self.a_undo)
        tb.addAction(self.a_redo)
        tb.addSeparator()
        tb.addAction(self.a_zoom_out)
        self.scale_title = QLabel()
        tb.addWidget(self.scale_title)
        self.scale_combo = QComboBox()
        self.scale_combo.setEditable(True)
        self.scale_combo.setMinimumWidth(110)
        self.scale_combo.addItem("")  # "Fit", set in retranslate()
        for n in SCALE_PRESETS:
            self.scale_combo.addItem(f"1:{n}")
        self.scale_combo.activated.connect(lambda _index: self._scale_from_combo())
        self.scale_combo.lineEdit().returnPressed.connect(self._scale_from_combo)
        tb.addWidget(self.scale_combo)
        tb.addAction(self.a_zoom_in)
        tb.addAction(self.a_fit)
        tb.addSeparator()
        self.reference_title = QLabel()
        tb.addWidget(self.reference_title)
        self.reference_combo = QComboBox()
        for code in ("md", "tvd", "tvdss"):
            self.reference_combo.addItem(code.upper(), code)
        self.reference_combo.activated.connect(
            lambda index: self.set_depth_reference(self.reference_combo.itemData(index))
        )
        tb.addWidget(self.reference_combo)
        tb.addSeparator()
        for a in (self.a_add_track, self.a_tops, self.a_petro, self.a_calc, self.a_zones):
            tb.addAction(a)
        tb.addSeparator()
        for a in (self.a_xplot, self.a_corr, self.a_map, self.a_table, self.a_export):
            tb.addAction(a)
        for a in (self.a_zoom_out, self.a_zoom_in, self.a_undo, self.a_redo):
            button = tb.widgetForAction(a)
            font = button.font()
            font.setPointSizeF(font.pointSizeF() * 1.4)
            font.setBold(True)
            button.setFont(font)
            button.setMinimumWidth(30)

    def retranslate(self):
        """Sets every visible text in the current language."""
        texts = {
            # action: (menu text, toolbar text or None, status tip or None)
            self.a_open: (_("Open LAS…"), _("Open LAS"), _("Open one or more LAS files")),
            self.a_open_proj: (_("Open project…"), None, None),
            self.a_save_proj: (_("Save project"), _("Save"), None),
            self.a_save_proj_as: (_("Save project as…"), None, None),
            self.a_export: (_("Export log (PDF / PNG)…"), _("Export"), None),
            self.a_export_las: (_("Export LAS (with computed curves)…"), None, None),
            self.a_export_csv: (_("Export CSV…"), None, None),
            self.a_quit: (_("Quit"), None, None),
            self.a_tpl_save: (_("Save template of the active well…"), None, None),
            self.a_tpl_load: (_("Load template and apply to the active well…"), None, None),
            self.a_tpl_all: (_("Apply the active well's layout to all wells"), None, None),
            self.a_tpl_default: (_("Use the active well's layout as the default template"), None, None),
            self.a_tpl_reset: (_("Reset default template (Triple Combo)"), None, None),
            self.a_tpl_triple: (_("Rebuild Triple Combo in the active well"), None, None),
            self.a_aliases: (
                _("Mnemonic aliases…"),
                None,
                _("Curve names of your company, recognized when opening wells and applying templates"),
            ),
            self.a_add_track: (_("Add track"), _("+ Track"), None),
            self.a_edit_track: (_("Edit selected track…"), None, None),
            self.a_del_track: (_("Remove selected track"), None, None),
            self.a_tops: (_("Formation tops…"), _("Tops"), None),
            self.a_survey: (_("Deviation survey, elevation and location…"), None, None),
            self.a_intervals: (_("Intervals (perforations, tests, comments)…"), None, None),
            self.a_core: (_("Import core data (CSV)…"), None, None),
            self.reference_actions["md"]: (_("Measured depth (MD)"), None, None),
            self.reference_actions["tvd"]: (_("True vertical depth (TVD)"), None, None),
            self.reference_actions["tvdss"]: (_("True vertical depth subsea (TVDSS)"), None, None),
            self.unit_actions["file"]: (_("As in the file"), None, None),
            self.unit_actions["m"]: (_("Meters"), None, None),
            self.unit_actions["ft"]: (_("Feet"), None, None),
            self.a_petro: (_("Petrophysics (Vsh, φ, Sw)…"), _("Petrophysics"), None),
            self.a_calc: (_("Curve calculator…"), _("Calculator"), None),
            self.a_curve_tools: (_("Edit curve (depth shift, despike, smoothing)…"), None, None),
            self.a_normalize: (_("Normalize a curve between wells…"), None, None),
            self.a_zones: (_("Zone summary (net pay)…"), _("Zones"), None),
            self.a_stats: (_("Statistics and histogram…"), None, None),
            self.a_table: (_("Data table"), _("Data"), None),
            self.a_xplot: (_("Crossplot…"), _("Crossplot"), None),
            self.a_nd: (_("Neutron-density crossplot…"), None, None),
            self.a_pickett: (_("Pickett plot…"), None, None),
            self.a_corr: (_("Well correlation…"), _("Correlation"), None),
            self.a_map: (_("Base map…"), _("Map"), None),
            self.a_fit: (_("Fit to window"), _("Fit"), None),
            self.a_zoom_in: (_("Zoom in"), "+", _("Zoom in to the next standard scale")),
            self.a_zoom_out: (_("Zoom out"), "−", _("Zoom out to the next standard scale")),
            self.a_tile: (_("Tile"), None, None),
            self.a_cascade: (_("Cascade"), None, None),
            self.a_tabs: (_("Show as tabs"), None, None),
            self.a_help: (_("Navigation and shortcuts"), None, None),
            self.a_about: (_("About InnoPetrol"), None, None),
            self.a_equations: (_("Equations and references"), None, None),
        }
        for action, (text, icon_text, tip) in texts.items():
            action.setText(text)
            action.setIconText(icon_text or text)
            action.setStatusTip(tip or "")
            action.setToolTip(text)
        for a in (self.a_zoom_out, self.a_zoom_in, self.a_fit):
            a.setToolTip(f"{a.text()} ({key_text(a.shortcut())})")

        self.m_file.setTitle(_("&File"))
        self.m_edit.setTitle(_("&Edit"))
        self._undo_texts()
        self.recent_menu.setTitle(_("Open recent"))
        self.m_template.setTitle(_("&Template"))
        self.m_well.setTitle(_("&Well"))
        self.m_analysis.setTitle(_("&Analysis"))
        self.m_view.setTitle(_("&View"))
        self.scale_menu.setTitle(_("Vertical scale"))
        self.reference_menu.setTitle(_("Depth reference"))
        self.unit_menu.setTitle(_("Depth unit"))
        self.system_menu.setTitle(_("Unit system"))
        for code, action in self.system_actions.items():
            action.setText(_(units.SYSTEMS[code][0]))
        self.system_actions[self.settings.value("unit_system") or "file"].setChecked(True)
        self.reference_title.setText(" " + _("Depth") + " ")
        self.language_menu.setTitle("Language / Idioma")  # bilingual on purpose: findable in any language
        self.m_help.setTitle(_("&Help"))
        self.language_actions[i18n.current_language()].setChecked(True)

        self.toolbar.setWindowTitle(_("Main"))
        self.scale_title.setText(" " + _("Scale") + " ")
        self.scale_combo.setItemText(0, _("Fit"))
        self.dock.setWindowTitle(_("Wells"))
        self.tree.retranslate()
        self._refresh_recent()
        self._update_title()
        self.statusBar().showMessage(
            _("Ready. Open a LAS file ({shortcut}) or drag it onto the window.").format(
                shortcut=key_text(QKeySequence.StandardKey.Open)
            )
        )
        for view in self.views.values():
            view.canvas.invalidate()  # texts drawn on the log ("not available", depth unit…)
        v = self.active_view()
        if v:
            self._show_scale(v)

    def _undo_texts(self):
        """“Undo Remove track” / “Redo Add track”: the menu says what will be undone."""
        for action, label, text, icon in (
            (self.a_undo, _("Undo"), self.undo_group.undoText(), "↶"),
            (self.a_redo, _("Redo"), self.undo_group.redoText(), "↷"),
        ):
            action.setText(f"{label}: {text}" if text else label)
            action.setIconText(icon)
            action.setToolTip(f"{action.text()} ({key_text(action.shortcut())})")

    def set_language(self, code: str):
        """Switches the interface language at runtime and remembers it."""
        code = i18n.set_language(code)
        self.settings.setValue("language", code)
        app = QApplication.instance()
        if app is not None:
            i18n.install_qt_translator(app, code)
        # Auxiliary windows (crossplot, data table, correlation…) are closed; reopening them
        # shows them in the new language.
        for w in list(self._windows):
            w.close()
        self.retranslate()

    def _update_actions(self):
        has = bool(self.docs)
        for a in self.findChildren(QAction):
            if a.property("needs_doc"):
                a.setEnabled(has)
        self.a_corr.setEnabled(len(self.docs) >= 2)
        self.scale_combo.setEnabled(has)
        self._refresh_depth_controls()

    # ================================================================== active well

    def active_view(self) -> WellView | None:
        sub = self.mdi.activeSubWindow() or self.mdi.currentSubWindow()
        widget = sub.widget() if sub is not None else None
        if isinstance(widget, WellView):
            return widget
        return self.views.get(self.docs[0]) if len(self.docs) == 1 else None

    def active_doc(self) -> WellDocument | None:
        v = self.active_view()
        if v is None and self.docs:
            self.statusBar().showMessage(_("Select a well window."), 4000)
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
            self.undo_group.setActiveStack(v.doc.undo_stack)
            self.tree.select_doc(v.doc)
            self._show_scale(v)
            self._refresh_depth_controls()

    def _refresh_depth_controls(self):
        """Checks/enables the depth reference and unit controls for the active well."""
        v = self.active_view()
        doc = v.doc if v else None
        has_elevation = doc is not None and doc.well.elevation is not None
        self.reference_actions["tvdss"].setEnabled(has_elevation)
        reference = doc.view.reference if doc else "md"
        self.reference_actions[reference].setChecked(True)
        self.unit_actions[doc.display_unit or "file" if doc else "file"].setChecked(True)
        self.reference_combo.setEnabled(doc is not None)
        self.reference_combo.setCurrentIndex(self.reference_combo.findData(reference))
        model = self.reference_combo.model()
        model.item(self.reference_combo.findData("tvdss")).setEnabled(has_elevation)

    def set_depth_reference(self, reference: str):
        doc = self.active_doc()
        if not doc:
            return
        if reference == "tvdss" and doc.well.elevation is None:
            self.statusBar().showMessage(
                _("TVDSS needs the elevation of the depth reference (Well ▸ Deviation survey and elevation…)."), 6000
            )
            self._refresh_depth_controls()
            return
        if reference != "md" and doc.well.survey is None:
            self.statusBar().showMessage(
                _("{well} has no deviation survey: it is drawn as a vertical well (TVD = MD).").format(well=doc.title),
                6000,
            )
        self._keeping_view(doc, lambda: doc.set_depth_reference(reference))
        self._refresh_depth_controls()

    def set_display_unit(self, unit: str | None):
        doc = self.active_doc()
        if doc:
            self._keeping_view(doc, lambda: doc.set_display_unit(unit))
            self._refresh_depth_controls()

    def set_unit_system(self, system: str):
        """Unit system for every open well and for the ones opened later."""
        self.settings.setValue("unit_system", system)
        for doc in self.docs:
            self._keeping_view(doc, lambda doc=doc: doc.apply_unit_system(system))
            self.tree.refresh(doc)
        self.system_actions[system].setChecked(True)
        self._refresh_depth_controls()

    def set_curve_unit(self, doc, mnemonic: str, unit: str | None):
        doc.set_curve_unit(mnemonic, unit)
        self.tree.refresh(doc)

    def _keeping_view(self, doc, change):
        """Applies a depth display change keeping the same well depth centered and the same 1:N scale."""
        v = self.views.get(doc)
        if v is None:
            change()
            return
        c = v.canvas
        fit, ratio = c.fit_mode, c.current_scale()
        md_center = float(doc.view.to_md(c.depth_at(c.header_h + c.body_h / 2)))
        change()
        if not fit:
            c.set_scale(ratio)
            c.center_on(float(doc.view.to_display(md_center)))

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
            v.canvas.center_on(float(doc.view.to_display(depth)))  # tops are stored in MD

    def _show_scale(self, v: WellView):
        if v is not self.active_view():
            return
        text = _("Fit") if v.canvas.fit_mode else f"1:{v.canvas.current_scale():.0f}"
        self.scale_combo.blockSignals(True)
        self.scale_combo.setEditText(text)
        self.scale_combo.blockSignals(False)
        lo, hi = v.canvas.visible_depth_range()
        self.scale_label.setText(
            _("{well} · scale 1:{scale} · visible {top} – {bottom} {unit}").format(
                well=v.doc.title,
                scale=f"{v.canvas.current_scale():.0f}",
                top=f"{max(lo, v.doc.view.start):.1f}",
                bottom=f"{min(hi, v.doc.view.stop):.1f}",
                unit=v.doc.view.depth_unit,
            )
        )

    def _scale_from_combo(self):
        text = self.scale_combo.currentText().strip()
        v = self.active_view()
        if not v:
            return
        if text.lower() in (_("Fit").lower(), "fit", "ajustar"):
            v.canvas.fit()
            return
        try:
            n = float(text.split(":")[-1].replace(",", "."))
            if n <= 0:
                raise ValueError
        except ValueError:
            self.statusBar().showMessage(_("Type the scale as 1:500 or 500."), 4000)
            return
        v.canvas.set_scale(n)

    def _zoom_step(self, direction: int):
        v = self.active_view()
        if v:
            v.canvas.zoom_step(direction)

    def _set_scale(self, n):
        v = self.active_view()
        if v:
            v.canvas.set_scale(n)

    # ================================================================== opening wells

    def open_las_dialog(self):
        start = self.settings.value("last_dir", str(Path.home()))
        paths, _filter = QFileDialog.getOpenFileNames(
            self,
            _("Open well files"),
            start,
            _("Well logs (*.las *.LAS *.dlis *.DLIS);;LAS (*.las *.LAS);;DLIS (*.dlis *.DLIS);;All files (*)"),
        )
        if paths:
            self.settings.setValue("last_dir", str(Path(paths[0]).parent))
            self.open_las(paths)

    def open_las(self, paths):
        errors, opened, corrected = [], [], []
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            for path in paths:
                try:
                    wells = load_wells(path)  # LAS: one well; DLIS: one per depth frame
                except Exception as e:
                    errors.append(f"{Path(path).name}: {e}")
                    continue
                self._add_recent(path)
                for well in wells:
                    layout, missing = self._default_layout(well)
                    doc = self.add_doc(well, layout)
                    opened.append(doc.title)
                    if missing:
                        self.statusBar().showMessage(
                            _("{well}: the default template uses curves that are not in the well: {curves}").format(
                                well=doc.title, curves=", ".join(missing)
                            ),
                            8000,
                        )
                    if well.notes:
                        corrected.append(f"{doc.title}: " + "; ".join(well.notes))
        finally:
            QApplication.restoreOverrideCursor()
        if errors:
            QMessageBox.warning(self, _("Open LAS"), _("Could not open:") + "\n\n" + "\n".join(errors))
        if opened and not errors:
            self.statusBar().showMessage(_("Loaded: {wells}").format(wells=", ".join(opened)), 5000)
        if corrected:
            # Engineers must know when their data was altered on load.
            QMessageBox.information(
                self,
                _("Data corrected on load"),
                _("Some problems in the files were corrected:") + "\n\n" + "\n".join(corrected),
            )

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

    def add_doc(
        self,
        well,
        layout,
        petro=None,
        depth_reference: str = "md",
        display_unit: str | None = None,
        curve_units: dict | None = None,
    ) -> WellDocument:
        doc = WellDocument(well, layout, petro, self)
        doc.depth_reference, doc.display_unit = depth_reference, display_unit
        if curve_units is None:
            doc.adopt_layout(layout)  # template scales -> this well's units
            system = self.settings.value("unit_system") or "file"
            if system != "file":
                doc.apply_unit_system(system)
        else:
            doc.curve_units = dict(curve_units)
        doc.reset_history()  # opening a well is not an undoable change
        self.undo_group.addStack(doc.undo_stack)
        self.undo_group.setActiveStack(doc.undo_stack)
        view = WellView(doc)
        sub = self.mdi.addSubWindow(view)
        sub.setWindowIcon(app_icon())
        sub.resize(
            min(int(sum(t.width for t in layout.tracks)) + 40, max(self.mdi.width() - 20, 400)),
            max(self.mdi.height() - 20, 400),
        )
        view.statusMessage.connect(lambda msg: self.statusBar().showMessage(msg))
        view.exportRequested.connect(self.export_log)
        view.statsRequested.connect(lambda d, interval: self.show_stats(d, None, interval))
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
            self.undo_group.removeStack(doc.undo_stack)
            self.tree.remove_doc(doc)
            self._update_actions()

    # The session keeps this state; these properties keep the window's simple API.
    @property
    def dirty(self) -> bool:
        return self.session.dirty

    @dirty.setter
    def dirty(self, value: bool) -> None:
        self.session.dirty = value

    @property
    def project_path(self) -> Path | None:
        return self.session.project_path

    @project_path.setter
    def project_path(self, path: Path | None) -> None:
        self.session.project_path = path

    @property
    def recovery(self):
        return self.session.recovery

    @property
    def data_dir(self) -> Path:
        return self.session.data_dir

    def _mark_dirty(self):
        self.dirty = True

    def _add_recent(self, path):
        self.session.add_recent(path)
        self._refresh_recent()

    def _refresh_recent(self):
        self.recent_menu.clear()
        recent = self.session.recent()
        for p in recent:
            a = self.recent_menu.addAction(Path(p).name)
            a.setStatusTip(p)
            if p.lower().endswith(PROJECT_SUFFIX):
                a.triggered.connect(lambda _checked=False, p=p: self.open_project(p))
            else:
                a.triggered.connect(lambda _checked=False, p=p: self.open_las([p]))
        self.recent_menu.setEnabled(bool(recent))

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        projects = [p for p in paths if p.lower().endswith(PROJECT_SUFFIX)]
        if projects:
            self.open_project(projects[0])
        wells = [p for p in paths if is_well_file(p)]
        if wells:
            self.open_las(wells)

    # ================================================================== project

    def _project_filter(self) -> str:
        return _("InnoPetrol project (*{suffix})").format(suffix=PROJECT_SUFFIX)

    def open_project_dialog(self):
        path, _filter = QFileDialog.getOpenFileName(
            self, _("Open project"), self.settings.value("last_dir", ""), self._project_filter()
        )
        if path:
            self.open_project(path)

    def autosave(self) -> bool:
        return self.session.autosave(self.docs)

    def check_recovery(self) -> None:
        """At startup: offers to restore the work of a session that did not close properly."""
        if not self.recovery.pending():
            return
        saved, _project = self.recovery.info()
        r = QMessageBox.question(
            self,
            _("Recover work"),
            _("InnoPetrol did not close properly last time. Restore the work saved automatically at {time}?").format(
                time=saved
            )
            + "\n\n"
            + _("If you choose No, the saved copy is deleted."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
        )
        if r == QMessageBox.StandardButton.Yes:
            self.restore_autosave()
        elif r == QMessageBox.StandardButton.No:
            self.recovery.discard()

    def open_project(self, path) -> None:
        if self._load_project_file(path):
            self.session.opened(path)
            self._refresh_recent()
            self._update_title()

    def restore_autosave(self) -> None:
        """Opens the autosaved work. It stays attached to the project it came from, still unsaved."""
        if self._load_project_file(self.recovery.path):
            self.session.restored()
            self._update_title()

    def _load_project_file(self, path) -> bool:
        """Replaces the open wells with those of a project file. False if nothing was opened."""
        if self.docs and not self._confirm_discard():
            return False
        try:
            result = load_project(path)
        except ProjectError as e:
            QMessageBox.warning(self, _("Open project"), str(e))
            return False
        self._close_all()
        for entry in result.entries:
            self.add_doc(
                entry.well, entry.layout, entry.petro, entry.depth_reference, entry.display_unit, entry.curve_units
            )
        if result.errors:
            QMessageBox.warning(
                self, _("Open project"), _("Some items could not be loaded:") + "\n\n" + "\n".join(result.errors)
            )
        return True

    def save_project(self, ask: bool = False) -> bool:
        if not self.docs:
            return False
        path = self.project_path
        if ask or path is None:
            default = path or Path.home() / (_("project") + PROJECT_SUFFIX)
            name, _filter = QFileDialog.getSaveFileName(self, _("Save project"), str(default), self._project_filter())
            if not name:
                return False
            path = Path(name if name.lower().endswith(PROJECT_SUFFIX) else name + PROJECT_SUFFIX)
        try:
            self.session.save(self.docs, path)
        except OSError as e:
            QMessageBox.warning(self, _("Save project"), _("Could not save: {error}").format(error=e))
            return False
        self._refresh_recent()
        self._update_title()
        self.statusBar().showMessage(_("Project saved to {path}").format(path=path), 5000)
        return True

    def _update_title(self):
        name = f" — {self.project_path.name}" if self.project_path else ""
        self.setWindowTitle(_("InnoPetrol — Well Viewer") + name)

    def _close_all(self):
        for v in list(self.views.values()):
            v.confirm_close = False
            v.parentWidget().close()

    def _confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        r = QMessageBox.question(
            self,
            _("Unsaved changes"),
            _("Save the current project before continuing?"),
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
        )
        if r == QMessageBox.StandardButton.Save:
            return self.save_project()
        return r == QMessageBox.StandardButton.Discard

    def closeEvent(self, e):
        if self.docs and not self._confirm_discard():
            e.ignore()
            return
        self.settings.setValue("geometry", self.saveGeometry())
        self._close_all()
        self.session.closed_normally()  # nothing to recover
        e.accept()

    # ================================================================== templates

    def _template_filter(self) -> str:
        return _("InnoPetrol template (*{suffix} *.json)").format(suffix=TEMPLATE_SUFFIX)

    def save_template(self):
        doc = self.active_doc()
        if not doc:
            return
        path, _filter = QFileDialog.getSaveFileName(
            self, _("Save template"), _("template") + TEMPLATE_SUFFIX, self._template_filter()
        )
        if path:
            if not path.lower().endswith(".json"):
                path += TEMPLATE_SUFFIX
            save_template(path, doc.layout)
            self.statusBar().showMessage(_("Template saved: {path}").format(path=path), 5000)

    def load_template(self):
        doc = self.active_doc()
        if not doc:
            return
        path, _filter = QFileDialog.getOpenFileName(self, _("Load template"), "", self._template_filter())
        if not path:
            return
        try:
            layout = load_template(path)
        except (TemplateError, OSError) as e:
            QMessageBox.warning(self, _("Load template"), str(e))
            return
        self._apply_layout(doc, layout)

    def _apply_layout(self, doc, layout) -> list[str]:
        result, missing = apply_template(layout, doc.well)
        # Template scales -> this well's display units.
        doc.set_layout(doc.adopt_layout(result), _("Apply template"))
        if missing:
            self.statusBar().showMessage(
                _("{well}: curves not found: {curves}").format(well=doc.title, curves=", ".join(missing)), 8000
            )
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
                    report.append(_("{well}: missing {curves}").format(well=other.title, curves=", ".join(missing)))
        QMessageBox.information(
            self, _("Apply to all"), _("Layout applied.") + ("\n\n" + "\n".join(report) if report else "")
        )

    def set_default_template(self):
        doc = self.active_doc()
        if not doc:
            return
        name = _("layout of {well}").format(well=doc.title)
        self.settings.setValue("default_template_json", template_to_json(doc.layout))
        self.settings.setValue("default_template_name", name)
        self.tree.set_template_name(name)
        self.statusBar().showMessage(_("Default template updated: it will be used for newly opened wells."), 5000)

    def reset_default_template(self):
        self.settings.remove("default_template_json")
        self.settings.remove("default_template_name")
        self.tree.set_template_name(None)

    def _load_aliases(self):
        from innopetrol.model import mnemonics

        text = self.settings.value("mnemonic_aliases")
        try:
            mnemonics.set_user_aliases(mnemonics.aliases_from_json(text) if text else {})
        except ValueError:
            mnemonics.set_user_aliases({})

    def edit_aliases(self):
        from innopetrol.model import mnemonics
        from innopetrol.ui.aliases_dialog import AliasesDialog

        dialog = AliasesDialog(self)
        if dialog.exec():
            aliases = dialog.aliases()
            mnemonics.set_user_aliases(aliases)
            self.settings.setValue("mnemonic_aliases", mnemonics.aliases_to_json(aliases))
            self.statusBar().showMessage(
                _(
                    "Aliases saved: they apply to wells opened and templates applied from "
                    "now on (Template ▸ Rebuild Triple Combo for an open well)."
                ),
                8000,
            )

    def rebuild_triple_combo(self):
        doc = self.active_doc()
        if doc:
            doc.set_layout(doc.adopt_layout(build_triple_combo(doc.well)), _("Rebuild Triple Combo"))

    # ================================================================== tools

    def edit_survey(self):
        doc = self.active_doc()
        if doc:
            from innopetrol.ui.survey_dialog import SurveyDialog

            if SurveyDialog(doc, self).exec():
                self.tree.refresh(doc)
                self._refresh_depth_controls()

    def edit_tops(self, doc):
        if doc:
            from innopetrol.ui.tops_dialog import TopsDialog

            TopsDialog(doc, self).exec()

    def petrophysics(self):
        doc = self.active_doc()
        if doc:
            from innopetrol.ui.petro_dialog import PetroDialog

            PetroDialog(doc, self).exec()

    def curve_tools(self, doc, curve: str | None = None):
        if doc:
            from innopetrol.ui.curve_tools_dialog import CurveToolsDialog

            CurveToolsDialog(doc, curve, self).exec()

    def normalize_curves(self):
        doc = self.active_doc()
        if doc:
            from innopetrol.ui.normalize_dialog import NormalizeDialog

            NormalizeDialog(self.docs, doc, self).exec()

    def calculator(self):
        doc = self.active_doc()
        if doc:
            from innopetrol.ui.calculator_dialog import CalculatorDialog

            CalculatorDialog(doc, self).exec()

    def zone_summary(self):
        doc = self.active_doc()
        if doc:
            from innopetrol.ui.zone_summary_dialog import ZoneSummaryDialog

            ZoneSummaryDialog(doc, self).exec()

    def show_stats(self, doc, curve: str | None = None, interval: tuple[float, float] | None = None):
        if doc:
            from innopetrol.ui.analysis import StatsDialog

            self._modeless(StatsDialog(doc, curve, self, self.docs, interval))

    def import_core(self):
        doc = self.active_doc()
        if not doc:
            return
        from innopetrol.model.core import load_core_csv
        from innopetrol.ui.core_dialog import CoreDialog

        path, _filter = QFileDialog.getOpenFileName(
            self,
            _("Import core data"),
            self.settings.value("last_dir", ""),
            _("Core data (*.csv *.txt);;All files (*)"),
        )
        if not path:
            return
        try:
            table = load_core_csv(path)
        except (OSError, ValueError) as e:
            QMessageBox.warning(
                self,
                _("Import core data"),
                _("The file needs a header row with a depth column and numeric columns ({error}).").format(error=e),
            )
            return
        CoreDialog(doc, table, path, self).exec()

    def edit_intervals(self, doc):
        if doc:
            from innopetrol.ui.intervals_dialog import IntervalsDialog

            IntervalsDialog(doc, self).exec()

    def data_table(self):
        doc = self.active_doc()
        if doc:
            from innopetrol.ui.analysis import DataTableWindow

            self._modeless(DataTableWindow(doc, self))

    def crossplot(self, mode: str):
        doc = self.active_doc()
        if doc:
            from innopetrol.ui.crossplot import CrossplotWindow

            self._modeless(CrossplotWindow(doc, mode, self, self.docs))

    def base_map(self):
        from innopetrol.ui.base_map import BaseMapWindow

        if not any(d.well.location is not None for d in self.docs):
            QMessageBox.information(
                self,
                _("Base map"),
                _(
                    "None of the open wells has coordinates in its header. "
                    "Enter them in Well ▸ Deviation survey, elevation and "
                    "location…"
                ),
            )
            return
        window = BaseMapWindow(self.docs, self)
        window.correlateRequested.connect(self.correlation)
        window.wellActivated.connect(self.activate_doc)
        self._modeless(window)

    def correlation(self, docs=None):
        """Correlation of the open wells, or of `docs` in that order (a section picked on the map)."""
        from innopetrol.ui.correlation import CorrelationSetup, CorrelationWindow

        docs = list(docs) if docs else self.docs
        if len(docs) < 2:
            QMessageBox.information(self, _("Correlation"), _("Open at least two wells."))
            return
        setup = CorrelationSetup(docs, self)
        if setup.exec():
            docs = setup.selected()
            if len(docs) < 1:
                return
            self._modeless(
                CorrelationWindow(
                    docs, setup.datum.currentData(), self, setup.tracks.currentData(), setup.reference.currentData()
                )
            )

    def show_equations(self):
        from innopetrol.ui.equations_dialog import EquationsDialog

        self._modeless(EquationsDialog(self))

    def _modeless(self, w):
        w.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._windows.append(w)
        w.destroyed.connect(lambda _obj=None, w=w: self._windows.remove(w) if w in self._windows else None)
        w.show()

    def _delete_curve(self, doc, name):
        r = QMessageBox.question(self, _("Delete curve"), _("Delete the computed curve {name}?").format(name=name))
        if r == QMessageBox.StandardButton.Yes:
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
        path, _filter = QFileDialog.getSaveFileName(self, _("Export LAS"), f"{doc.title}.las", "LAS (*.las)")
        if path:
            try:
                doc.well.to_las(path)
                self.statusBar().showMessage(_("LAS exported: {path}").format(path=path), 5000)
            except Exception as e:
                QMessageBox.warning(self, _("Export LAS"), _("Could not export: {error}").format(error=e))

    def export_csv(self):
        doc = self.active_doc()
        if not doc:
            return
        path, _filter = QFileDialog.getSaveFileName(self, _("Export CSV"), f"{doc.title}.csv", "CSV (*.csv)")
        if path:
            try:
                doc.well.to_csv(path)
                self.statusBar().showMessage(_("CSV exported: {path}").format(path=path), 5000)
            except OSError as e:
                QMessageBox.warning(self, _("Export CSV"), _("Could not export: {error}").format(error=e))

    def _toggle_tabs(self):
        self.mdi.setViewMode(
            QMdiArea.ViewMode.TabbedView if self.a_tabs.isChecked() else QMdiArea.ViewMode.SubWindowView
        )
        self.mdi.setTabsClosable(True)
        self.mdi.setTabsMovable(True)
