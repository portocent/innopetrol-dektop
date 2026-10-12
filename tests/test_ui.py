"""Pruebas de la interfaz en modo offscreen (sin ventana real)."""

import math

import pytest
from PySide6.QtCore import QSettings

from innopetrol.model.tops import Top
from innopetrol.ui.main_window import MainWindow


@pytest.fixture
def win(qtbot, tmp_path, samples):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.IniFormat)
    w = MainWindow(settings)
    qtbot.addWidget(w)
    w.resize(1400, 900)
    w.show()
    w.open_las([str(samples / "Testdata.las"), str(samples / "TotalDepthPrueba.las")])
    yield w
    w.dirty = False
    for v in w.views.values():
        v.confirm_close = False


def test_open_wells(win):
    assert [d.title for d in win.docs] == ["Test Well 1", "1-5"]
    assert win.tree.topLevelItemCount() == 3  # plantilla + 2 pozos


def test_close_well_updates_tree(win, samples):
    doc = win.docs[0]
    view = win.views[doc]
    view.confirm_close = False
    view.parentWidget().close()
    assert [d.title for d in win.docs] == ["1-5"]
    texts = [win.tree.topLevelItem(i).text(0) for i in range(win.tree.topLevelItemCount())]
    assert "Test Well 1" not in texts and "1-5" in texts
    # Reabrir no pisa el ítem del otro pozo (bug del código original)
    win.open_las([str(samples / "Testdata.las")])
    texts = [win.tree.topLevelItem(i).text(0) for i in range(win.tree.topLevelItemCount())]
    assert texts.count("1-5") == 1 and texts.count("Test Well 1") == 1


def test_canvas_navigation(win, qtbot):
    view = win.views[win.docs[0]]
    c = view.canvas
    qtbot.waitExposed(c)
    c.set_scale(500)
    assert c.current_scale() == pytest.approx(500)
    c.center_on(8000)
    lo, hi = c.visible_depth_range()
    assert lo < 8000 < hi
    c.zoom(2, anchor_depth=8000)
    assert c.current_scale() == pytest.approx(250)
    lo2, hi2 = c.visible_depth_range()
    assert lo2 < 8000 < hi2 and (hi2 - lo2) < (hi - lo)
    c.fit()
    lo, hi = c.visible_depth_range()
    assert lo <= win.docs[0].well.start + 1 and hi >= win.docs[0].well.stop - 1
    readout = c.readout(8000)
    assert "SGR" in readout and "8000.00" in readout


def test_track_editor_roundtrip(win):
    from innopetrol.ui.track_editor import TrackEditor

    doc = win.docs[0]
    before = doc.layout.tracks[0]
    ed = TrackEditor(doc, 0, win)
    ed.title_edit.setText("GR modificado")
    assert ed._apply()
    after = doc.layout.tracks[0]
    assert after.title == "GR modificado"
    assert [c.mnemonic for c in after.curves] == [c.mnemonic for c in before.curves]
    assert len(after.fills) == len(before.fills)


def test_track_editor_validation(win, monkeypatch):
    from innopetrol.ui import track_editor

    warnings = []
    monkeypatch.setattr(track_editor.QMessageBox, "warning", staticmethod(lambda *a: warnings.append(a[2])))
    ed = track_editor.TrackEditor(win.docs[0], 2, win)  # resistividad (log)
    ed.curve_table.cellWidget(0, track_editor.C_LEFT).setText("-1")
    assert not ed._apply()
    assert "logarítmica" in warnings[0]
    ed.curve_table.cellWidget(0, track_editor.C_LEFT).setText("abc")
    assert not ed._apply()


def test_track_management(win):
    view = win.views[win.docs[0]]
    n = len(win.docs[0].layout.tracks)
    view.canvas.selected = 0
    view.add_track("depth")
    assert len(win.docs[0].layout.tracks) == n + 1 and win.docs[0].layout.tracks[1].is_depth
    view.canvas.selected = 1
    view.move_track(1)
    assert win.docs[0].layout.tracks[2].is_depth
    view.canvas.selected = 2
    view.remove_track()
    assert len(win.docs[0].layout.tracks) == n


def test_petro_and_zones(win):
    from innopetrol.ui.petro_dialog import PetroDialog, ZoneSummaryDialog

    doc = win.docs[0]
    doc.set_tops([Top("A", 7790), Top("B", 8040)])
    PetroDialog(doc, win)._run()
    assert {"VSH", "PHIE", "SW", "PAY_FLAG"} <= set(doc.well.curves)
    titles = [t.title for t in doc.layout.tracks]
    assert titles.index("Resultados petrofísicos") == titles.index("Densidad - Neutrón") + 1
    z = ZoneSummaryDialog(doc, win)
    assert [r[0] for r in z._rows] == ["(sobre el primer tope)", "A", "B"]


def test_calculator_dialog(win):
    from innopetrol.ui.petro_dialog import CalculatorDialog

    doc = win.docs[0]
    d = CalculatorDialog(doc, win)
    d.name.setText("dphi2")
    d.expr.setPlainText("(2.65 - RHOB) / 1.65")
    d._ok()
    assert doc.well.curves["DPHI2"].formula == "(2.65 - RHOB) / 1.65"
    d = CalculatorDialog(doc, win)
    d.name.setText("RHOB")
    d.expr.setPlainText("RHOB * 2")
    d._ok()  # no puede reemplazar una curva original
    assert doc.well.curves["RHOB"].formula is None


def test_windows_open(win, qtbot):
    from innopetrol.ui.analysis import DataTableWindow, StatsDialog
    from innopetrol.ui.correlation import CorrelationWindow
    from innopetrol.ui.crossplot import CrossplotWindow

    a, b = win.docs
    a.set_tops([Top("X", 7800)])
    b.set_tops([Top("X", 5550)])
    for mode in ("free", "nd", "pickett"):
        x = CrossplotWindow(a, mode, win)
        x.show()
    s = StatsDialog(a, "SGR", win)
    t = DataTableWindow(a, win)
    t.show()
    a.cursorMoved.emit(8000.0)
    assert t.view.currentIndex().row() == 772  # (8000 - 7614) / 0.5
    c = CorrelationWindow([a, b], "X", win, 3)
    c.show()
    qtbot.waitUntil(lambda: c.canvases[0].body_h > 100)
    c._apply_scale()
    ya = c.canvases[0].y_of(7800)
    yb = c.canvases[1].y_of(5550)
    assert math.isclose(ya, yb, abs_tol=1)  # aplanado: el tope X queda a la misma altura


def test_project_and_template(win, tmp_path):
    from innopetrol.model.template import load_template, save_template

    win.project_path = tmp_path / "p.ipproj"
    assert win.save_project()
    save_template(tmp_path / "t.ipt.json", win.docs[0].layout)
    win._apply_layout(win.docs[1], load_template(tmp_path / "t.ipt.json"))
    names = {c.mnemonic for t in win.docs[1].layout.tracks for c in t.curves}
    assert "GR" in names and "ILD" in names
    win.dirty = False
    win.open_project(str(tmp_path / "p.ipproj"))
    assert [d.title for d in win.docs] == ["Test Well 1", "1-5"]
