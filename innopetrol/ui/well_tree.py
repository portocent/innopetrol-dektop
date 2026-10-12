"""Side tree: the wells of the project, with header information, curves and tops.

Each well item keeps its WellRef (ROLE_REF) and, when the well is loaded, its document (ROLE_DOC).
The original code looked items up by title text or by position, and got out of sync when wells were
closed. Wells that are not loaded show their summary; those children are built only when the item
is expanded, so a project with hundreds of wells does not create thousands of items up front.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import QMenu, QTreeWidget, QTreeWidgetItem

from innopetrol.i18n import _
from innopetrol.model import units
from innopetrol.model.catalog import WellRef, WellSummary, matches, matching_curves
from innopetrol.model.equations import EQUATIONS, curve_equations
from innopetrol.model.intervals import KINDS as INTERVAL_KINDS
from innopetrol.model.mnemonics import FAMILIES, family_of
from innopetrol.ui.document import WellDocument

ROLE_DOC = Qt.ItemDataRole.UserRole
ROLE_KIND = Qt.ItemDataRole.UserRole + 1
ROLE_NAME = Qt.ItemDataRole.UserRole + 2
ROLE_REF = Qt.ItemDataRole.UserRole + 3


class WellTree(QTreeWidget):
    docActivated = Signal(object)
    curveStatsRequested = Signal(object, str)
    curveEditRequested = Signal(object, str)
    curveDeleteRequested = Signal(object, str)
    curveUnitRequested = Signal(object, str, object)  # doc, mnemonic, unit (None = file unit)
    topsRequested = Signal(object)
    intervalsRequested = Signal(object)
    topActivated = Signal(object, float)
    # Lists of WellRef (one or several selected wells)
    refsOpenRequested = Signal(list)  # load if needed and show their windows
    refsLoadRequested = Signal(list)
    refsUnloadRequested = Signal(list)
    refsRemoveRequested = Signal(list)
    refsCorrelateRequested = Signal(list)
    countChanged = Signal(int, int)  # wells shown by the filter, wells in the project

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self._text_filter, self._curve_filter = "", ""
        self._hidden = 0  # well items hidden by the filter (kept up to date: counting is O(1))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        self.itemDoubleClicked.connect(self._double_click)
        self.itemExpanded.connect(self._expanded)
        self.template_item = QTreeWidgetItem([""])
        self._template_name: str | None = None
        self.set_template_name(None)
        self.template_item.setForeground(0, QBrush(QColor("#566573")))
        self.addTopLevelItem(self.template_item)

    def set_template_name(self, name: str | None):
        self._template_name = name
        self.template_item.setText(0, _("Default template: {name}").format(name=name or _("automatic Triple Combo")))

    def retranslate(self):
        self.set_template_name(self._template_name)
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            ref, doc = item.data(0, ROLE_REF), item.data(0, ROLE_DOC)
            if doc is not None:
                self.refresh(doc)
            elif ref is not None:
                self.set_doc(ref, None)

    def _item_for(self, doc) -> QTreeWidgetItem | None:
        for i in range(self.topLevelItemCount()):
            it = self.topLevelItem(i)
            if it is not None and it.data(0, ROLE_DOC) is doc:
                return it
        return None

    def _item_for_ref(self, ref) -> QTreeWidgetItem | None:
        for i in range(self.topLevelItemCount()):
            it = self.topLevelItem(i)
            if it is not None and it.data(0, ROLE_REF) is ref:
                return it
        return None

    def add_ref(self, ref: WellRef, doc: WellDocument | None = None) -> None:
        item = QTreeWidgetItem()
        item.setData(0, ROLE_REF, ref)
        self.addTopLevelItem(item)
        self._fill(item, ref, doc)
        self._apply_filter(item)
        self.countChanged.emit(*self.counts())

    def set_doc(self, ref: WellRef, doc: WellDocument | None) -> None:
        """The well was loaded (doc) or unloaded (None)."""
        item = self._item_for_ref(ref)
        if item is not None:
            expanded = item.isExpanded()
            item.takeChildren()
            self._fill(item, ref, doc)
            item.setExpanded(expanded)
            self._apply_filter(item)
            self.countChanged.emit(*self.counts())

    def remove_ref(self, ref) -> None:
        it = self._item_for_ref(ref)
        if it is not None:
            self._hidden -= it.isHidden()
            self.takeTopLevelItem(self.indexOfTopLevelItem(it))
            self.countChanged.emit(*self.counts())

    def _fill(self, item: QTreeWidgetItem, ref: WellRef, doc: WellDocument | None) -> None:
        item.setData(0, ROLE_DOC, doc)
        if doc is not None:
            item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicatorWhenChildless)
            item.setForeground(0, self.palette().text())
            self._populate(item, doc)
            item.setExpanded(True)
            doc.curvesChanged.connect(lambda: self.refresh(doc))
            doc.topsChanged.connect(lambda: self.refresh(doc))
            return
        font = QFont(self.font())
        font.setItalic(True)
        item.setFont(0, font)
        item.setText(0, ref.name + ("  " + _("(file not found)") if ref.missing else ""))
        item.setForeground(0, QBrush(QColor("#c0392b" if ref.missing else "#566573")))
        item.setToolTip(0, _("{path}\nNot loaded: double-click to open it.").format(path=ref.path or ""))
        item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)

    def _expanded(self, item: QTreeWidgetItem) -> None:
        ref = item.data(0, ROLE_REF)
        if ref is not None and item.data(0, ROLE_DOC) is None and item.childCount() == 0:
            _add_summary(item, ref.summary)
            self._mark_curves(item)

    # ---------------------------------------------------------------- filter
    def _well_items(self) -> list[QTreeWidgetItem]:
        items = (self.topLevelItem(i) for i in range(self.topLevelItemCount()))
        return [it for it in items if it is not None and it.data(0, ROLE_REF) is not None]

    def counts(self) -> tuple[int, int]:
        """(wells shown by the filter, wells in the tree)."""
        total = self.topLevelItemCount() - 1  # the first item is the default template
        return total - self._hidden, total

    def set_filter(self, text: str, curve: str) -> None:
        """Show only the wells whose name, UWI, field or company contain the words of `text` and that
        have `curve` (a family key or a mnemonic); the matching curves are shown in bold."""
        self._text_filter, self._curve_filter = text, curve
        for item in self._well_items():
            self._apply_filter(item)
        self.countChanged.emit(*self.counts())

    @staticmethod
    def _summary(item: QTreeWidgetItem) -> WellSummary:
        doc = item.data(0, ROLE_DOC)
        return WellSummary.from_well(doc.well) if doc is not None else item.data(0, ROLE_REF).summary

    def _apply_filter(self, item: QTreeWidgetItem) -> None:
        hidden = bool(self._text_filter or self._curve_filter) and not matches(
            self._summary(item), self._text_filter, self._curve_filter
        )
        self._hidden += hidden - item.isHidden()
        item.setHidden(hidden)
        self._mark_curves(item)

    def _mark_curves(self, item: QTreeWidgetItem) -> None:
        """Bold the curves of a well that match the "with the curve…" filter."""
        children = [c for c in (item.child(i) for i in range(item.childCount())) if c is not None]
        curves = next((c for c in children if c.data(0, ROLE_KIND) == "curves"), None)
        if curves is None:
            return
        wanted = set(matching_curves(self._summary(item), self._curve_filter)) if self._curve_filter else set()
        for i in range(curves.childCount()):
            child = curves.child(i)
            if child is not None:
                font = child.font(0)
                font.setBold(child.data(0, ROLE_NAME) in wanted)
                child.setFont(0, font)

    def refresh(self, doc):
        it = self._item_for(doc)
        if it is None:
            return
        expanded = {it.child(i).text(0): it.child(i).isExpanded() for i in range(it.childCount())}
        it.takeChildren()
        self._populate(it, doc)
        for i in range(it.childCount()):
            child = it.child(i)
            child.setExpanded(expanded.get(child.text(0), child.isExpanded()))
        self._apply_filter(it)

    def select_doc(self, doc):
        it = self._item_for(doc)
        if it is not None:
            self.setCurrentItem(it)

    def _populate(self, item: QTreeWidgetItem, doc: WellDocument):
        w = doc.well
        bold = QFont(self.font())
        bold.setBold(True)
        item.setText(0, doc.title)
        item.setFont(0, bold)
        item.setToolTip(0, str(w.path) if w.path else doc.title)
        self._add_info(item, w)
        self._add_curves(item, doc)
        self._add_tops(item, doc)

    @staticmethod
    def _add_info(parent: QTreeWidgetItem, w) -> None:
        """Elevation, survey, corrections made on load, interval and header items."""
        info = QTreeWidgetItem(parent, [_("Well information")])
        if w.elevation is not None:
            text = _("Reference elevation: {value} {unit}").format(value=f"{w.elevation:g}", unit=w.depth_unit)
            QTreeWidgetItem(info, [text])
        if w.survey is not None:
            text = _("Deviation survey: {count} stations, max. inclination {inc}°").format(
                count=w.survey.md.size, inc=f"{w.survey.max_inclination:.1f}"
            )
            QTreeWidgetItem(info, [text])
        if w.notes:
            fixes = QTreeWidgetItem(info, [_("Corrections on load ({count})").format(count=len(w.notes))])
            fixes.setForeground(0, QBrush(QColor("#b9770e")))
            for note in w.notes:
                QTreeWidgetItem(fixes, [note])
        interval = _("Interval: {start} – {stop} {unit} (step {step})").format(
            start=f"{w.start:g}", stop=f"{w.stop:g}", unit=w.depth_unit, step=f"{w.step:g}"
        )
        QTreeWidgetItem(info, [interval])
        for h in w.header:
            if h.mnemonic.upper() not in ("STRT", "STOP", "STEP") and str(h.value).strip():
                child = QTreeWidgetItem(info, [f"{h.mnemonic}: {h.value} {h.unit}".strip()])
                child.setToolTip(0, h.description)

    @staticmethod
    def _add_curves(parent: QTreeWidgetItem, doc: WellDocument) -> None:
        w = doc.well
        curves = QTreeWidgetItem(parent, [_("Curves ({count})").format(count=len(w.curves))])
        curves.setData(0, ROLE_KIND, "curves")
        curves.setExpanded(True)
        for m, c in w.curves.items():
            ci = QTreeWidgetItem(curves, [_curve_label(doc, m, c)])
            ci.setData(0, ROLE_DOC, doc)
            ci.setData(0, ROLE_KIND, "curve")
            ci.setData(0, ROLE_NAME, m)
            if c.formula:
                ci.setForeground(0, QBrush(QColor("#1f618d")))
            ci.setToolTip(0, _curve_tooltip(c, curve_equations(m, doc.petro, "VSH" in w.curves)))

    @staticmethod
    def _add_tops(parent: QTreeWidgetItem, doc: WellDocument) -> None:
        w = doc.well
        tops = QTreeWidgetItem(parent, [_("Tops ({count})").format(count=len(w.tops))])
        tops.setData(0, ROLE_DOC, doc)
        tops.setData(0, ROLE_KIND, "tops")
        for t in w.tops:
            ti = QTreeWidgetItem(tops, [f"{t.name}: {t.depth:g} {w.depth_unit}"])
            ti.setForeground(0, QBrush(QColor(t.color)))
            ti.setData(0, ROLE_DOC, doc)
            ti.setData(0, ROLE_KIND, "top")
            ti.setData(0, ROLE_NAME, t.depth)
        intervals = QTreeWidgetItem(parent, [_("Intervals ({count})").format(count=len(w.intervals))])
        intervals.setData(0, ROLE_DOC, doc)
        intervals.setData(0, ROLE_KIND, "intervals")
        for i in w.intervals:
            text = f"{i.top:g}–{i.base:g} {w.depth_unit}  {i.label or _(INTERVAL_KINDS[i.kind][0])}"
            item = QTreeWidgetItem(intervals, [text])
            item.setForeground(0, QBrush(QColor(i.shown_color)))
            item.setData(0, ROLE_DOC, doc)
            item.setData(0, ROLE_KIND, "top")  # double-click goes to that depth, like a top
            item.setData(0, ROLE_NAME, i.top)

    def _doc_of(self, item) -> WellDocument | None:
        while item is not None:
            d = item.data(0, ROLE_DOC)
            if d is not None:
                return d
            item = item.parent()
        return None

    @staticmethod
    def _ref_of(item):
        while item is not None and item.parent() is not None:
            item = item.parent()
        return item.data(0, ROLE_REF) if item is not None else None

    def _double_click(self, item, _col):
        doc = self._doc_of(item)
        if doc is None:
            ref = self._ref_of(item)
            if ref is not None:
                self.refsOpenRequested.emit([ref])
            return
        kind = item.data(0, ROLE_KIND)
        if kind == "curve":
            self.curveStatsRequested.emit(doc, item.data(0, ROLE_NAME))
        elif kind == "top":
            self.topActivated.emit(doc, float(item.data(0, ROLE_NAME)))
        elif kind == "tops":
            self.topsRequested.emit(doc)
        elif kind == "intervals":
            self.intervalsRequested.emit(doc)
        else:
            self.docActivated.emit(doc)

    def _menu(self, pos):
        item = self.itemAt(pos)
        doc, ref = self._doc_of(item), self._ref_of(item)
        if ref is None:
            return
        menu = QMenu(self)
        selected = self.selected_refs()
        if len(selected) > 1 and ref in selected:
            self._wells_menu(menu, selected)
            menu.exec(self.viewport().mapToGlobal(pos))
            return
        if doc is None:
            self._wells_menu(menu, [ref])
            menu.exec(self.viewport().mapToGlobal(pos))
            return
        if item.data(0, ROLE_KIND) == "curve":
            name = item.data(0, ROLE_NAME)
            menu.addAction(_("Statistics and histogram…")).triggered.connect(
                lambda: self.curveStatsRequested.emit(doc, name)
            )
            menu.addAction(_("Edit curve (depth shift, despike, smoothing)…")).triggered.connect(
                lambda: self.curveEditRequested.emit(doc, name)
            )
            options = units.convertible(doc.well.curves[name].unit)
            if not options and name in doc.curve_units:
                options = [
                    k for k, u in units.UNITS.items() if u.dimension == units.UNITS[doc.curve_units[name]].dimension
                ]
            if len(options) > 1:  # something to convert to
                sub = menu.addMenu(_("Display unit"))
                current = doc.curve_units.get(name)
                original = sub.addAction(_("As in the file ({unit})").format(unit=doc.well.curves[name].unit))
                original.setCheckable(True)
                original.setChecked(current is None)
                original.triggered.connect(lambda: self.curveUnitRequested.emit(doc, name, None))
                sub.addSeparator()
                for key in options:
                    a = sub.addAction(units.label(key))
                    a.setCheckable(True)
                    a.setChecked(current == key)
                    a.triggered.connect(lambda _checked=False, key=key: self.curveUnitRequested.emit(doc, name, key))
            if doc.well.curves[name].formula:
                menu.addAction(_("Delete computed curve")).triggered.connect(
                    lambda: self.curveDeleteRequested.emit(doc, name)
                )
        menu.addAction(_("Show well window")).triggered.connect(lambda: self.docActivated.emit(doc))
        menu.addAction(_("Edit tops…")).triggered.connect(lambda: self.topsRequested.emit(doc))
        menu.addSeparator()
        menu.addAction(_("Unload from memory")).triggered.connect(lambda: self.refsUnloadRequested.emit([ref]))
        menu.addAction(_("Remove from project…")).triggered.connect(lambda: self.refsRemoveRequested.emit([ref]))
        menu.exec(self.viewport().mapToGlobal(pos))

    def selected_refs(self) -> list[WellRef]:
        """The selected wells, in tree order."""
        selected = {id(self._ref_of(it)) for it in self.selectedItems()}
        return [it.data(0, ROLE_REF) for it in self._well_items() if id(it.data(0, ROLE_REF)) in selected]

    def _wells_menu(self, menu: QMenu, refs: list[WellRef]) -> None:
        """Actions on one or several wells (several: the count is shown)."""
        n = f" ({len(refs)})" if len(refs) > 1 else ""
        menu.addAction(_("Open") + n).triggered.connect(lambda: self.refsOpenRequested.emit(refs))
        menu.addAction(_("Load without opening a window") + n).triggered.connect(
            lambda: self.refsLoadRequested.emit(refs)
        )
        if len(refs) > 1:
            menu.addAction(_("Correlate") + n).triggered.connect(lambda: self.refsCorrelateRequested.emit(refs))
        menu.addSeparator()
        if any(it.data(0, ROLE_DOC) is not None for it in self._well_items() if it.data(0, ROLE_REF) in refs):
            menu.addAction(_("Unload from memory") + n).triggered.connect(lambda: self.refsUnloadRequested.emit(refs))
        menu.addAction(_("Remove from project…") + n).triggered.connect(lambda: self.refsRemoveRequested.emit(refs))


def _add_summary(parent: QTreeWidgetItem, summary: WellSummary) -> None:
    """Children of a well that is not loaded: what its summary tells."""
    info = QTreeWidgetItem(parent, [_("Well information")])
    interval = _("Interval: {start} – {stop} {unit}").format(
        start=f"{summary.start:g}", stop=f"{summary.stop:g}", unit=summary.depth_unit
    )
    QTreeWidgetItem(info, [interval])
    for label, value in (("UWI", summary.uwi), (_("Field"), summary.field_name), (_("Company"), summary.company)):
        if value:
            QTreeWidgetItem(info, [f"{label}: {value}"])
    if summary.location is not None:
        QTreeWidgetItem(info, [_("Location: {x:g}, {y:g}").format(x=summary.location.x, y=summary.location.y)])
    curves = QTreeWidgetItem(parent, [_("Curves ({count})").format(count=len(summary.curves))])
    curves.setData(0, ROLE_KIND, "curves")
    for mnemonic, unit in summary.curves:
        fam = FAMILIES.get(family_of(mnemonic) or "")
        text = mnemonic + (f"  [{unit}]" if unit else "") + (f"  · {_(fam.name)}" if fam else "")
        QTreeWidgetItem(curves, [text]).setData(0, ROLE_NAME, mnemonic)
    QTreeWidgetItem(parent, [_("Tops ({count})").format(count=summary.tops)])


def _curve_label(doc: WellDocument, mnemonic: str, curve) -> str:
    """ "RHOB  [G/C3 → kg/m³]  · Density  (computed)": unit (and display unit if converted) and family."""
    fam = FAMILIES.get(family_of(mnemonic) or "")
    unit_text = curve.unit
    if mnemonic in doc.curve_units:
        unit_text = f"{curve.unit or '?'} → {units.label(doc.curve_units[mnemonic])}"
    label = mnemonic + (f"  [{unit_text}]" if unit_text else "") + (f"  · {_(fam.name)}" if fam else "")
    return label + ("  " + _("(computed)") if curve.formula else "")


def _curve_tooltip(curve, equations: tuple[str, ...] = ()) -> str:
    tip = [curve.description] if curve.description else []
    if curve.has_data:
        tip.append(
            _("Min {min} · Max {max} · Mean {mean}").format(
                min=f"{curve.min:.4g}", max=f"{curve.max:.4g}", mean=f"{np.nanmean(curve.values):.4g}"
            )
        )
    if curve.formula:
        tip.append(f"= {curve.formula}")
    for key in equations:  # where the equation comes from (Help ▸ Equations and references)
        tip.append(f"{_(EQUATIONS[key].name)} — {EQUATIONS[key].reference}")
    return "\n".join(tip)
