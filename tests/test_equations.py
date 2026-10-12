"""Every method the user can choose has its equation and reference."""

import pytest

from innopetrol.model import petro
from innopetrol.model.equations import EQUATIONS, SECTIONS, TEMPERATURE_EQUATIONS, curve_equations


def test_every_method_has_an_equation():
    for methods in (petro.VSH_METHODS, petro.PHI_METHODS, petro.SW_MODELS):
        for key in methods:
            assert key in EQUATIONS, key
    assert set(TEMPERATURE_EQUATIONS) == set(petro.TEMP_MODES)
    shown = {k for _title, keys in SECTIONS for k in keys}
    assert shown == set(EQUATIONS)  # nothing hidden from the equations window
    for eq in EQUATIONS.values():
        assert eq.reference and eq.formula and eq.variables


def test_curve_equations_follow_the_parameters():
    p = petro.PetroParams(vsh_method="larionov_older", phi_method="nd_rms", sw_model="indonesia")
    assert curve_equations("VSH", p, True) == ("larionov_older",)
    assert curve_equations("PHIT", p, True) == ("density", "nd_rms")
    assert curve_equations("SW", p, True) == ("indonesia",)
    assert curve_equations("SW", p, False) == ("archie",)  # no Vsh: the program used Archie
    assert curve_equations("GR", p, True) == () and curve_equations("VSH", None, True) == ()


def test_dialogs(qtbot, testdata_well, monkeypatch):
    from PySide6.QtWidgets import QMessageBox, QToolButton

    from innopetrol.model.mnemonics import build_triple_combo
    from innopetrol.ui.document import WellDocument
    from innopetrol.ui.equations_dialog import EquationsDialog
    from innopetrol.ui.petro_dialog import PetroDialog

    d = EquationsDialog()
    qtbot.addWidget(d)
    text = d.browser.toPlainText()
    assert "Archie, G. E. (1942)" in text and "Poupon" in text and "Taylor" in text

    shown = []
    monkeypatch.setattr(QMessageBox, "exec", lambda box: shown.append(box.text()))
    dialog = PetroDialog(WellDocument(testdata_well, build_triple_combo(testdata_well)))
    qtbot.addWidget(dialog)
    dialog.sw_model.setCurrentIndex(dialog.sw_model.findData("simandoux"))
    buttons = [b for b in dialog.findChildren(QToolButton) if b.text() == "?"]
    assert len(buttons) == 4
    for b in buttons:
        b.click()
    assert any("Simandoux" in t for t in shown) and len(shown) == 4


@pytest.mark.parametrize("language", ["en", "es"])
def test_equation_texts_are_translated(language):
    from innopetrol import i18n
    from innopetrol.i18n import _

    i18n.set_language(language)
    names = {_(eq.name) for eq in EQUATIONS.values()}
    assert len(names) == len(EQUATIONS)
    if language == "es":
        assert _(EQUATIONS["archie"].name) != EQUATIONS["archie"].name
