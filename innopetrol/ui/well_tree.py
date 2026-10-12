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
from innopetrol.model.mnemonics import FAMILIES, family_of
from innopetrol.ui.document import WellDocument

ROLE_DOC = Qt.UserRole
ROLE_KIND = Qt.UserRole + 1
ROLE_NAME = Qt.UserRole + 2


class WellTree(QTreeWidget):
    docActivated = Signal(object)
    curveStatsRequested = Signal(object, str)
    curveDeleteRequested = Signal(object, str)
    topsRequested = Signal(object)
    topActivated = Signal(object, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
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
            if it.data(0, ROLE_DOC) is doc:
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

        info = QTreeWidgetItem(item, [_("Well information")])
        if w.notes:
            fixes = QTreeWidgetItem(info, [_("Corrections on load ({count})").format(count=len(w.notes))])
            fixes.setForeground(0, QBrush(QColor("#b9770e")))
            for note in w.notes:
                QTreeWidgetItem(fixes, [note])
        QTreeWidgetItem(info, [_("Interval: {start} – {stop} {unit} (step {step})").format(
            start=f"{w.start:g}", stop=f"{w.stop:g}", unit=w.depth_unit, step=f"{w.step:g}")])
        for h in w.header:
            if h.mnemonic.upper() in ("STRT", "STOP", "STEP"):
                continue
            if str(h.value).strip():
                child = QTreeWidgetItem(info, [f"{h.mnemonic}: {h.value} {h.unit}".strip()])
                child.setToolTip(0, h.description)

        curves = QTreeWidgetItem(item, [_("Curves ({count})").format(count=len(w.curves))])
        curves.setExpanded(True)
        for m, c in w.curves.items():
            fam = FAMILIES.get(family_of(m) or "")
            label = f"{m}" + (f"  [{c.unit}]" if c.unit else "") + (f"  · {_(fam.name)}" if fam else "")
            if c.formula:
                label += "  " + _("(computed)")
            ci = QTreeWidgetItem(curves, [label])
            ci.setData(0, ROLE_DOC, doc)
            ci.setData(0, ROLE_KIND, "curve")
            ci.setData(0, ROLE_NAME, m)
            if c.formula:
                ci.setForeground(0, QBrush(QColor("#1f618d")))
            tip = [c.description] if c.description else []
            if c.has_data:
                tip.append(_("Min {min} · Max {max} · Mean {mean}").format(
                    min=f"{c.min:.4g}", max=f"{c.max:.4g}", mean=f"{np.nanmean(c.values):.4g}"))
            if c.formula:
                tip.append(f"= {c.formula}")
            ci.setToolTip(0, "\n".join(tip))

        tops = QTreeWidgetItem(item, [_("Tops ({count})").format(count=len(w.tops))])
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
                lambda: self.curveStatsRequested.emit(doc, name))
            if doc.well.curves[name].formula:
                menu.addAction(_("Delete computed curve")).triggered.connect(
                    lambda: self.curveDeleteRequested.emit(doc, name))
        menu.addAction(_("Show well window")).triggered.connect(lambda: self.docActivated.emit(doc))
        menu.addAction(_("Edit tops…")).triggered.connect(lambda: self.topsRequested.emit(doc))
        menu.exec(self.viewport().mapToGlobal(pos))
