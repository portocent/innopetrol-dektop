"""Editor of the user's mnemonic aliases (each company names its curves differently)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
                               QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

from innopetrol.i18n import _
from innopetrol.model import mnemonics
from innopetrol.resources import app_icon

COL_FAMILY, COL_BUILTIN, COL_USER = range(3)
FILE_FILTER = "JSON (*.json)"


class AliasesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Mnemonic aliases"))
        self.setWindowIcon(app_icon())
        self.resize(900, 600)
        lay = QVBoxLayout(self)
        hint = QLabel(_("Add the curve names your company or service providers use, separated by commas. "
                        "They are recognized when opening wells and applying templates. A name written "
                        "here wins over a built-in one, so it can also move a mnemonic to another family."))
        hint.setWordWrap(True)
        lay.addWidget(hint)
        self.table = QTableWidget(len(mnemonics.FAMILIES), 3)
        self.table.setHorizontalHeaderLabels([_("Family"), _("Built-in names"), _("Your names")])
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_FAMILY, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(COL_BUILTIN, QHeaderView.Stretch)
        header.setSectionResizeMode(COL_USER, QHeaderView.Stretch)
        self.keys = list(mnemonics.FAMILIES)
        current = mnemonics.user_aliases()
        for r, key in enumerate(self.keys):
            fam = mnemonics.FAMILIES[key]
            for c, text in ((COL_FAMILY, _(fam.name)), (COL_BUILTIN, ", ".join(fam.aliases))):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if c == COL_BUILTIN:
                    item.setToolTip(text)
                self.table.setItem(r, c, item)
            self.table.setItem(r, COL_USER, QTableWidgetItem(", ".join(current.get(key, []))))
        lay.addWidget(self.table, 1)
        row = QHBoxLayout()
        for text, slot in ((_("Import…"), self._import), (_("Export…"), self._export)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        row.addWidget(buttons)
        lay.addLayout(row)

    def aliases(self) -> dict[str, list[str]]:
        out = {}
        for r, key in enumerate(self.keys):
            names = [a.strip() for a in self.table.item(r, COL_USER).text().replace(";", ",").split(",")]
            names = [a for a in names if a]
            if names:
                out[key] = names
        return out

    def set_aliases(self, aliases: dict[str, list[str]]) -> None:
        for r, key in enumerate(self.keys):
            self.table.item(r, COL_USER).setText(", ".join(aliases.get(key, [])))

    def _check(self) -> bool:
        conflicts = mnemonics.alias_conflicts(self.aliases())
        if conflicts:
            lines = [_("{alias}: {families}").format(
                alias=a, families=", ".join(_(mnemonics.FAMILIES[f].name) for f in fams)) for a, fams in conflicts]
            QMessageBox.warning(self, self.windowTitle(),
                                _("These names are in more than one family:") + "\n\n" + "\n".join(lines))
            return False
        return True

    def _ok(self):
        if self._check():
            self.accept()

    def _import(self):
        path, _filter = QFileDialog.getOpenFileName(self, _("Import aliases"), "", FILE_FILTER)
        if not path:
            return
        try:
            aliases = mnemonics.aliases_from_json(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, _("Import aliases"), _("Could not read the file: {error}").format(error=e))
            return
        unknown = sorted(set(aliases) - set(self.keys))
        self.set_aliases({k: v for k, v in aliases.items() if k in self.keys})
        if unknown:
            QMessageBox.information(self, _("Import aliases"),
                                    _("Unknown families were ignored: {families}").format(families=", ".join(unknown)))

    def _export(self):
        if not self._check():
            return
        path, _filter = QFileDialog.getSaveFileName(self, _("Export aliases"), _("aliases") + ".json", FILE_FILTER)
        if path:
            try:
                Path(path).write_text(mnemonics.aliases_to_json(self.aliases()), encoding="utf-8")
            except OSError as e:
                QMessageBox.warning(self, _("Export aliases"), _("Could not save: {error}").format(error=e))
