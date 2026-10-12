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
def no_modal_boxes(monkeypatch):
    """Los QMessageBox modales bloquearían las pruebas: se responden automáticamente."""
    from PySide6.QtWidgets import QMessageBox

    calls = []
    for name in ("warning", "information", "critical"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, _n=name, **k: calls.append((_n, a))))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    return calls
