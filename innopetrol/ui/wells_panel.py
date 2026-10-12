"""Side panel: the well tree with a search box, a "with the curve…" filter and a well count."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit, QVBoxLayout, QWidget

from innopetrol.i18n import _
from innopetrol.model.mnemonics import FAMILIES
from innopetrol.ui.well_tree import WellTree


class WellsPanel(QWidget):
    def __init__(self, tree: WellTree, parent=None):
        super().__init__(parent)
        self.tree = tree
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.curve = QComboBox()
        self.curve.setEditable(True)  # a family from the list, or any mnemonic typed in
        self.count = QLabel()
        for w in (self.search, self.curve, tree, self.count):
            lay.addWidget(w)
        self.retranslate()
        self.search.textChanged.connect(self._filter)
        self.curve.currentTextChanged.connect(self._filter)
        tree.countChanged.connect(self._show_count)

    def retranslate(self) -> None:
        self.search.setPlaceholderText(_("Search wells (name, UWI, field, company)"))
        self.curve.setToolTip(_("Show only the wells with this curve: a family, or a mnemonic typed in"))
        current = self.curve_filter()
        self.curve.blockSignals(True)
        self.curve.clear()
        self.curve.addItem(_("With any curve"), "")
        for key, family in sorted(FAMILIES.items(), key=lambda kv: _(kv[1].name)):
            self.curve.addItem(_("With {family}").format(family=_(family.name)), key)
        index = self.curve.findData(current)
        if index >= 0:
            self.curve.setCurrentIndex(index)
        else:
            self.curve.setEditText(current)
        self.curve.blockSignals(False)
        self._show_count(*self.tree.counts())

    def curve_filter(self) -> str:
        """The family key chosen in the list, or the mnemonic typed in."""
        text = self.curve.currentText()
        index = self.curve.findText(text)
        return self.curve.itemData(index) if index >= 0 else text.strip()

    def _filter(self) -> None:
        self.tree.set_filter(self.search.text(), self.curve_filter())

    def _show_count(self, shown: int, total: int) -> None:
        if shown == total:
            self.count.setText(_("{total} wells").format(total=total))
        else:
            self.count.setText(_("{shown} of {total} wells").format(shown=shown, total=total))
