"""Undo / redo: every content change is one step; display changes (units) are not undone."""

import numpy as np
import pytest

from innopetrol.model import petro
from innopetrol.model.layout import TrackSpec
from innopetrol.model.mnemonics import build_triple_combo
from innopetrol.model.tops import Top
from innopetrol.model.well import Curve
from innopetrol.ui.document import WellDocument


@pytest.fixture
def doc(testdata_well, qapp):
    return WellDocument(testdata_well, build_triple_combo(testdata_well))


def titles(doc):
    return [t.title for t in doc.layout.tracks]


def test_track_changes_undo_and_redo(doc):
    original = titles(doc)
    doc.remove_track(2)
    doc.insert_track(0, TrackSpec(title="NEW"))
    assert doc.undo_stack.count() == 2 and doc.undo_stack.undoText() == "Add track"
    doc.undo_stack.undo()
    doc.undo_stack.undo()
    assert titles(doc) == original
    doc.undo_stack.redo()
    assert len(doc.layout.tracks) == len(original) - 1
    doc.undo_stack.redo()
    assert titles(doc)[0] == "NEW"


def test_in_place_edits_are_recorded(doc):
    """Code that edits the layout directly and emits layoutChanged is also undoable."""
    doc.layout.tracks[0].width = 333
    doc.layoutChanged.emit()
    assert doc.undo_stack.count() == 1
    doc.undo_stack.undo()
    assert doc.layout.tracks[0].width != 333


def test_one_step_for_a_grouped_operation(doc):
    params = petro.PetroParams(gr_curve="SGR", rhob_curve="RHOB", rt_curve="LLD")
    with doc.undo_step("Compute petrophysics"):
        doc.petro = params
        doc.add_curves(petro.compute(doc.well, params))
        doc.insert_track(3, TrackSpec(title="Results"))
    assert doc.undo_stack.count() == 1
    doc.undo_stack.undo()
    assert "PHIE" not in doc.well.curves and doc.petro is None and "Results" not in titles(doc)
    doc.undo_stack.redo()
    assert "PHIE" in doc.well.curves and doc.petro.rt_curve == "LLD" and "SW" in doc.well.curves


def test_curves_and_tops(doc):
    curve = Curve("X", "", "", np.zeros_like(doc.well.depth), formula="GR * 0")
    doc.add_curves([curve])
    doc.set_tops([Top("A", 1000.0)])
    doc.remove_curve("X")
    doc.undo_stack.undo()
    assert doc.well.curves["X"] is curve  # the same object comes back, no copy
    doc.undo_stack.undo()
    assert doc.well.tops == []
    doc.undo_stack.undo()
    assert "X" not in doc.well.curves


def test_unit_changes_are_not_undone_and_restored_scales_follow_them(doc):
    doc.remove_track(0)
    doc.set_curve_unit("RHOB", "kg/m3")  # a display change: not a step
    assert doc.undo_stack.count() == 1
    doc.undo_stack.undo()
    style = next(c for t in doc.layout.tracks for c in t.curves if c.mnemonic == "RHOB")
    # The restored layout was saved in g/cm³ and is shown in the current display unit.
    assert (style.left, style.right, style.unit) == (1950, 2950, "kg/m3")


def test_window_menu_follows_the_active_well(qtbot, tmp_path, samples):
    from PySide6.QtCore import QSettings

    from innopetrol.ui.main_window import MainWindow

    w = MainWindow(QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat))
    qtbot.addWidget(w)
    w.show()
    w.open_las([str(samples / "Testdata.las")])
    doc = w.docs[0]
    assert not w.a_undo.isEnabled()  # opening a file is not an undoable change
    doc.remove_track(1)
    assert w.a_undo.isEnabled() and "Remove track" in w.a_undo.text()
    w.a_undo.trigger()
    assert w.a_redo.isEnabled() and not w.a_undo.isEnabled()
    w.dirty = False
    for v in w.views.values():
        v.confirm_close = False
