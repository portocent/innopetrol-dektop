"""Wells in the project, loaded and with a window: the three states in the main window."""

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox

from innopetrol.model.tops import Top
from innopetrol.ui.main_window import MainWindow


@pytest.fixture
def win(qtbot, tmp_path, samples):
    w = MainWindow(QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))
    qtbot.addWidget(w)
    w.open_las([str(samples / "Testdata.las"), str(samples / "TotalDepthPrueba.las")])
    yield w
    w.dirty = False


def well_items(w):
    return [w.tree.topLevelItem(i) for i in range(1, w.tree.topLevelItemCount())]


def test_project_opens_only_the_wells_that_were_shown(win, tmp_path, qtbot):
    second = win.docs[1]
    win.views[second].parentWidget().close()
    win.session.save(win._project_items(), tmp_path / "p.ipproj")

    w2 = MainWindow(QSettings(str(tmp_path / "s2.ini"), QSettings.Format.IniFormat))
    qtbot.addWidget(w2)
    w2.open_project(tmp_path / "p.ipproj")
    assert len(w2.wells) == 2
    assert [d.title for d in w2.docs] == ["Test Well 1"] and len(w2.views) == 1
    assert not w2.dirty
    # The other well is listed, not loaded; double-clicking it loads it and opens its window
    item = well_items(w2)[1]
    assert item.text(0) == "1-5" and item.childCount() == 0
    item.setExpanded(True)  # the summary is built on demand
    assert item.childCount() == 3
    w2.tree._double_click(item, 0)
    assert [d.title for d in w2.docs] == ["Test Well 1", "1-5"] and len(w2.views) == 2


def test_unload_keeps_the_changes(win, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    doc = win.docs[0]
    doc.set_tops([Top("A", 7700, "#ff0000")])
    ref = win.wells.ref_of(doc)
    win.unload_well(ref)
    assert ref not in win.wells.docs and doc not in win.views and len(win.wells) == 2
    [reloaded] = win.load_refs([ref])
    assert reloaded is not doc and [t.name for t in reloaded.well.tops] == ["A"]


def test_remove_from_project(win, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    ref = win.wells.refs[0]
    win.remove_well(ref)
    assert len(win.wells) == 1 and [d.title for d in win.docs] == ["1-5"] and len(win.views) == 1
    assert [i.text(0) for i in well_items(win)] == ["1-5"]
