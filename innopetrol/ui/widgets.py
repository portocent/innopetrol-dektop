"""Small reusable widgets."""

from __future__ import annotations

import sys

from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import QColorDialog, QComboBox, QDoubleSpinBox, QHBoxLayout, QPushButton, QWidget

from innopetrol.i18n import _
from innopetrol.model.layout import FILL_PATTERNS, LINE_STYLE_NAMES, LINE_STYLES
from innopetrol.resources import icon

# Modifier key as the user sees it: on Mac Qt maps what the code calls "Ctrl" to ⌘.
MOD = "⌘" if sys.platform == "darwin" else "Ctrl"


def key_text(seq) -> str:
    """Shortcut in the platform's notation: ⌘O on Mac, Ctrl+O on Windows/Linux."""
    return QKeySequence(seq).toString(QKeySequence.SequenceFormat.NativeText)


def spin(value: float, lo: float, hi: float, step: float = 0.01, decimals: int = 3) -> QDoubleSpinBox:
    """A number field with its range, step and decimals."""
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(decimals)
    s.setSingleStep(step)
    s.setValue(value)
    return s


def choice_combo(choices: dict[str, str], current: str | None) -> QComboBox:
    """Combo box of {key: display name marked with N_()}; the key is the item data."""
    combo = QComboBox()
    for key, name in choices.items():
        combo.addItem(_(name), key)
    combo.setCurrentIndex(max(combo.findData(current), 0))
    return combo


def curve_combo(well, current: str | None, optional: bool = True) -> QComboBox:
    """Curves of a well with their unit, optionally with "(none)" first; the mnemonic is the data."""
    combo = QComboBox()
    if optional:
        combo.addItem(_("(none)"), None)
    for m, curve in well.curves.items():
        combo.addItem(f"{m}  [{curve.unit}]" if curve.unit else m, m)
    combo.setCurrentIndex(max(combo.findData(current), 0))
    return combo


def row_of(*widgets: QWidget) -> QHBoxLayout:
    """Horizontal layout with the widgets in order."""
    row = QHBoxLayout()
    for w in widgets:
        row.addWidget(w)
    return row


def fill_zone_combo(combo: QComboBox, zone_names: list[str]) -> None:
    """Fills an interval selector with "Whole well" (data None) and zones by name, keeping the choice."""
    current = combo.currentData()
    combo.blockSignals(True)
    combo.clear()
    combo.addItem(_("Whole well"), None)
    for name in zone_names:
        combo.addItem(name, name)
    combo.setCurrentIndex(max(combo.findData(current), 0))
    combo.blockSignals(False)


def parse_float(text: str) -> float | None:
    """Parses a number, accepting a decimal comma. Returns None for empty text.

    Raises ValueError if the text is not a valid number.
    """
    t = text.strip().replace(",", ".")
    if not t:
        return None
    return float(t)


class ColorButton(QPushButton):
    colorChanged = Signal(str)

    def __init__(self, color: str = "#000000", parent=None):
        super().__init__(parent)
        self.setIconSize(QSize(28, 12))
        self.set_color(color)
        self.clicked.connect(self._pick)

    def color(self) -> str:
        return self._color

    def set_color(self, color: str):
        self._color = QColor(color).name()
        pm = QPixmap(28, 12)
        pm.fill(QColor(self._color))
        self.setIcon(QIcon(pm))
        self.setToolTip(self._color)

    def _pick(self):
        c = QColorDialog.getColor(QColor(self._color), self, _("Choose color"))
        if c.isValid():
            self.set_color(c.name())
            self.colorChanged.emit(self._color)


class LineStyleCombo(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setIconSize(QSize(60, 14))
        for s in LINE_STYLES:
            self.addItem(icon(f"{s}.png"), _(LINE_STYLE_NAMES[s]), s)

    def value(self) -> str:
        return self.currentData()

    def set_value(self, style: str):
        i = self.findData(style)
        self.setCurrentIndex(max(i, 0))


class PatternCombo(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setIconSize(QSize(48, 16))
        for i, pat in enumerate(FILL_PATTERNS):
            self.addItem(icon(f"d{i + 1}.png"), "", pat)

    def value(self) -> str:
        return self.currentData()

    def set_value(self, pattern: str):
        i = self.findData(pattern)
        self.setCurrentIndex(max(i, 0))
