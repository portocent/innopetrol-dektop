"""Wells in the project, loaded and with a window: the three states in the main window."""

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox

from innopetrol.model.tops import Top
from innopetrol.ui.main_window import MainWindow
from innopetrol.ui.well_tree import ROLE_KIND, ROLE_NAME


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
    win.unload_wells([ref])
    assert ref not in win.wells.docs and doc not in win.views and len(win.wells) == 2
    [reloaded] = win.load_refs([ref])
    assert reloaded is not doc and [t.name for t in reloaded.well.tops] == ["A"]


def test_remove_from_project(win, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    ref = win.wells.refs[0]
    win.remove_wells([ref])
    assert len(win.wells) == 1 and [d.title for d in win.docs] == ["1-5"] and len(win.views) == 1
    assert [i.text(0) for i in well_items(win)] == ["1-5"]


def test_filter_by_text_and_curve(win):
    panel = win.wells_panel
    assert panel.count.text() == "2 wells"
    panel.search.setText("hugoton")  # field of 1-5
    assert [i.text(0) for i in well_items(win) if not i.isHidden()] == ["1-5"]
    assert panel.count.text() == "1 of 2 wells"
    panel.search.clear()
    panel.curve.setEditText("pef")  # a mnemonic typed in, any case
    assert [i.text(0) for i in well_items(win) if not i.isHidden()] == ["1-5"]
    panel.curve.setCurrentIndex(panel.curve.findData("sonic"))  # a family
    shown = [i for i in well_items(win) if not i.isHidden()]
    assert [i.text(0) for i in shown] == ["Test Well 1"]
    curves = next(
        shown[0].child(k) for k in range(shown[0].childCount()) if shown[0].child(k).data(0, ROLE_KIND) == "curves"
    )
    bold = [curves.child(k).data(0, ROLE_NAME) for k in range(curves.childCount()) if curves.child(k).font(0).bold()]
    assert bold == ["DTLN"]


def test_correlate_wells_selected_in_the_tree(win, monkeypatch):
    seen = []
    monkeypatch.setattr(win, "correlation", lambda docs=None: seen.append([d.title for d in docs]))
    for item in well_items(win):
        item.setSelected(True)
    refs = win.tree.selected_refs()
    win.unload_wells([refs[1]])
    win.tree.refsCorrelateRequested.emit(refs)
    assert seen == [["Test Well 1", "1-5"]]  # the unloaded one was loaded first
