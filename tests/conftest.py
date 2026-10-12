import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


@pytest.fixture
def samples():
    return SAMPLES


@pytest.fixture
def testdata_well():
    from innopetrol.model.well import Well

    return Well.from_las(SAMPLES / "Testdata.las")


@pytest.fixture(autouse=True)
def english(monkeypatch):
    """Tests run in English regardless of the machine's language."""
    from innopetrol import i18n

    monkeypatch.setattr(i18n, "system_language", lambda: "en")
    i18n.set_language("en")
    yield
    i18n.set_language("en")


@pytest.fixture(autouse=True)
def no_modal_boxes(monkeypatch):
    """Modal QMessageBoxes would block the tests, so they are answered automatically."""
    from PySide6.QtWidgets import QMessageBox

    calls = []
    for name in ("warning", "information", "critical"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, _n=name, **k: calls.append((_n, a))))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    return calls


@pytest.fixture(autouse=True)
def builtin_aliases():
    """User mnemonic aliases are global: every test starts and ends with the built-in ones."""
    from innopetrol.model import mnemonics

    mnemonics.set_user_aliases({})
    yield
    mnemonics.set_user_aliases({})
