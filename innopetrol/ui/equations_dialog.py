"""Equations and references: the formulas behind every result, with their sources."""

from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QMessageBox, QTextBrowser, QVBoxLayout, QWidget

from innopetrol.i18n import _
from innopetrol.model.equations import EQUATIONS, SECTIONS, Equation
from innopetrol.resources import app_icon


def equation_html(eq: Equation, heading: str = "h3") -> str:
    """One equation as HTML: name, formula, variables, note and reference."""
    rows = "".join(f"<tr><td><i>{symbol}</i></td><td>{_(text)}</td></tr>" for symbol, text in eq.variables)
    return (
        f"<{heading}>{_(eq.name)}</{heading}>"
        f"<p style='font-size:large; margin-left:16px'>{eq.formula}</p>"
        f"<table cellspacing=4>{rows}</table>"
        f"<p>{_(eq.note)}</p>"
        f"<p style='color:#566573'>{html.escape(eq.reference)}</p>"
    )


def show_equation(parent: QWidget, keys: tuple[str, ...] | list[str]) -> None:
    """Shows the equations of a method (e.g. the Sw model chosen in the petrophysics dialog)."""
    text = "<hr>".join(equation_html(EQUATIONS[k]) for k in keys)
    box = QMessageBox(
        QMessageBox.Icon.NoIcon,
        _("Equation"),
        text or _("No equation: Rw is the same at every depth."),
        QMessageBox.StandardButton.Close,
        parent,
    )
    box.setTextFormat(Qt.TextFormat.RichText)
    box.exec()


class EquationsDialog(QDialog):
    """Every equation InnoPetrol uses, grouped by subject."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Equations and references"))
        self.setWindowIcon(app_icon())
        self.resize(760, 680)
        lay = QVBoxLayout(self)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        parts = [
            "<p>"
            + _(
                "Every result is computed with these equations. Computed curves also keep their exact formula, "
                "shown in the well tree."
            )
            + "</p>"
        ]
        for title, keys in SECTIONS:
            parts.append(f"<h2>{_(title)}</h2>")
            parts += [equation_html(EQUATIONS[k]) for k in keys]
        self.browser.setHtml("".join(parts))
        lay.addWidget(self.browser)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
