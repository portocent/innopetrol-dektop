"""Side tree: open wells, header information, curves and tops.

Each item keeps a direct reference to its document (Qt.UserRole). The original code looked
items up by title text or by position, and got out of sync when wells were closed.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import QMenu, QTreeWidget, QTreeWidgetItem

from innopetrol.i18n import _
from innopetrol.model import units
from innopetrol.model.equations import EQUATIONS, curve_equations
from innopetrol.model.mnemonics import FAMILIES, family_of
from innopetrol.ui.document import WellDocument

ROLE_DOC = Qt.ItemDataRole.UserRole
ROLE_KIND = Qt.ItemDataRole.UserRole + 1
ROLE_NAME = Qt.ItemDataRole.UserRole + 2


class WellTree(QTreeWidget):
    docActivated = Signal(object)
    curveStatsRequested = Signal(object, str)
    curveDeleteRequested = Signal(object, str)
    curveUnitRequested = Signal(object, str, object)  # doc, mnemonic, unit (None = file unit)
    topsRequested = Signal(object)
    topActivated = Signal(object, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        self.itemDoubleClicked.connect(self._double_click)
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
            doc = self.topLevelItem(i).data(0, ROLE_DOC)
            if doc is not None:
                self.refresh(doc)

    def _item_for(self, doc) -> QTreeWidgetItem | None:
        for i in range(self.topLevelItemCount()):
            it = self.topLevelItem(i)
            if it is not None and it.data(0, ROLE_DOC) is doc:
                return it
        return None

    def add_doc(self, doc: WellDocument):
        item = QTreeWidgetItem()
        item.setData(0, ROLE_DOC, doc)
        self.addTopLevelItem(item)
        self._populate(item, doc)
        item.setExpanded(True)
        doc.curvesChanged.connect(lambda: self.refresh(doc))
        doc.topsChanged.connect(lambda: self.refresh(doc))

    def remove_doc(self, doc):
        it = self._item_for(doc)
        if it is not None:
            self.takeTopLevelItem(self.indexOfTopLevelItem(it))

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

    def _doc_of(self, item) -> WellDocument | None:
        while item is not None:
            d = item.data(0, ROLE_DOC)
            if d is not None:
                return d
            item = item.parent()
        return None

    def _double_click(self, item, _col):
        doc = self._doc_of(item)
        if doc is None:
            return
        kind = item.data(0, ROLE_KIND)
        if kind == "curve":
            self.curveStatsRequested.emit(doc, item.data(0, ROLE_NAME))
        elif kind == "top":
            self.topActivated.emit(doc, float(item.data(0, ROLE_NAME)))
        elif kind == "tops":
            self.topsRequested.emit(doc)
        else:
            self.docActivated.emit(doc)

    def _menu(self, pos):
        item = self.itemAt(pos)
        doc = self._doc_of(item)
        if doc is None:
            return
        menu = QMenu(self)
        if item.data(0, ROLE_KIND) == "curve":
            name = item.data(0, ROLE_NAME)
            menu.addAction(_("Statistics and histogram…")).triggered.connect(
                lambda: self.curveStatsRequested.emit(doc, name)
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
        menu.exec(self.viewport().mapToGlobal(pos))


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
