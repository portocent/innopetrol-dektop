"""Interval selection on the log, intervals track, synchronized cursor and core data."""

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QFileDialog, QInputDialog

from innopetrol.model.core import core_mnemonic, load_core_csv, place_on_grid
from innopetrol.model.intervals import Interval, kind_from_text, load_intervals_csv
from innopetrol.model.layout import TrackSpec
from innopetrol.model.mnemonics import build_triple_combo
from innopetrol.model.project import WellEntry, load_project, save_project
from innopetrol.model.tops import Top
from innopetrol.render.painter import DepthTransform, draw_track_body
from innopetrol.ui.document import WellDocument


@pytest.fixture
def view(testdata_well, qtbot):
    from innopetrol.ui.well_view import WellView

    doc = WellDocument(testdata_well, build_triple_combo(testdata_well))
    v = WellView(doc)
    qtbot.addWidget(v)
    v.resize(900, 700)
    v.show()
    qtbot.waitExposed(v)
    v.canvas.set_scale(500)
    v.canvas.center_on(7900)
    return v


# ---------------------------------------------------------------- selection


def test_drag_selects_an_interval_and_a_click_clears_it(view, qtbot):
    c = view.canvas
    x = 40
    y0, y1 = c.header_h + 100, c.header_h + 300
    qtbot.mousePress(c, Qt.MouseButton.LeftButton, pos=QPoint(x, int(y0)))
    qtbot.mouseMove(c, QPoint(x, int(y0 + 100)))
    qtbot.mouseMove(c, QPoint(x, int(y1)))
    qtbot.mouseRelease(c, Qt.MouseButton.LeftButton, pos=QPoint(x, int(y1)))
    top, base = c.interval
    assert top == pytest.approx(c.depth_at(y0), abs=0.5) and base == pytest.approx(c.depth_at(y1), abs=0.5)
    md = view.selection_md()
    assert md == pytest.approx((top, base))  # MD reference: display depth is MD
    qtbot.mouseClick(c, Qt.MouseButton.LeftButton, pos=QPoint(x, int(y0 + 50)))
    assert c.interval is None
    c.set_interval((7950, 7900))  # any order
    assert c.interval == (7900, 7950)
    qtbot.keyClick(c, Qt.Key.Key_Escape)
    assert c.interval is None


def test_selection_actions(view, qtbot, monkeypatch, tmp_path):
    c, doc = view.canvas, view.doc
    c.set_interval((7800.0, 7850.0))
    c.zoom_to_interval()
    top, bottom = c.visible_depth_range()
    assert top <= 7800 and bottom >= 7850 and bottom - top < 60
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("Sand X", True)))
    view.zone_from_selection()
    assert [(t.name, t.depth) for t in doc.well.tops] == [("Sand X", 7800.0), ("Base of Sand X", 7850.0)]
    out = tmp_path / "sel.csv"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(out), "CSV (*.csv)")))
    view.export_selection()
    depths = np.loadtxt(out, delimiter=",", skiprows=1, usecols=0, encoding="utf-8-sig")
    assert depths.min() >= 7800 and depths.max() < 7850 and depths.size == 100  # base excluded, like zones
    requested = []
    view.statsRequested.connect(lambda d, interval: requested.append(interval))
    view.statsRequested.emit(doc, view.selection_md())
    assert requested == [(7800.0, 7850.0)]


def test_statistics_of_the_selection(testdata_well, qtbot):
    from innopetrol.ui.analysis import StatsDialog

    doc = WellDocument(testdata_well, build_triple_combo(testdata_well))
    d = StatsDialog(doc, "SGR", interval=(7800.0, 7850.0))
    qtbot.addWidget(d)
    assert d.zone.currentData() == (7800.0, 7850.0) and "Valid samples: 100" in d.stats.text()


# ---------------------------------------------------------------- intervals


def test_intervals_csv_in_spanish(tmp_path):
    p = tmp_path / "i.csv"
    p.write_text("Desde;Hasta;Tipo;Descripción\n7800;7810,5;Punzado;Arena A\n7900;7920;DST 1;\n", encoding="utf-8")
    intervals = load_intervals_csv(p)
    assert [(i.top, i.base, i.kind, i.label) for i in intervals] == [
        (7800, 7810.5, "perforation", "Arena A"),
        (7900, 7920, "test", ""),
    ]
    assert kind_from_text("Pérdida de circulación") == "loss" and kind_from_text("whatever") == "comment"


def test_intervals_are_undoable_saved_and_drawn(testdata_well, tmp_path, qapp):
    w = testdata_well
    doc = WellDocument(w, build_triple_combo(w))
    doc.set_intervals([Interval(7900, 7950, "perforation", "Perf 1"), Interval(7820, 7830, "comment", "Note")])
    assert [i.label for i in w.intervals] == ["Note", "Perf 1"]  # kept sorted
    doc.undo_stack.undo()
    assert w.intervals == []
    doc.undo_stack.redo()
    save_project(tmp_path / "p.ipproj", [WellEntry(w, doc.layout)])
    assert load_project(tmp_path / "p.ipproj").entries[0].well.intervals == w.intervals

    img = QImage(120, 200, QImage.Format.Format_RGB32)
    img.fill(Qt.GlobalColor.white)
    p = QPainter(img)
    draw_track_body(p, QRectF(0, 0, 120, 200), TrackSpec(kind="intervals"), doc.view, DepthTransform(7880, 2.0))
    p.end()
    inside, outside = QColor(img.pixel(60, 60)), QColor(img.pixel(60, 190))  # 7910 vs 7975 ft
    assert inside != QColor(Qt.GlobalColor.white) and inside.red() > inside.blue()  # perforation red
    assert outside.red() <= outside.blue()  # white or the gray grid: no interval there


def test_intervals_dialog(testdata_well, qtbot, no_modal_boxes):
    from PySide6.QtWidgets import QLineEdit

    from innopetrol.ui.intervals_dialog import COL_BASE, IntervalsDialog

    doc = WellDocument(testdata_well, build_triple_combo(testdata_well))
    d = IntervalsDialog(doc, new=Interval(7800, 7850, "perforation"))
    qtbot.addWidget(d)
    assert d.table.rowCount() == 1
    d._cell(0, COL_BASE, QLineEdit).setText("7800")
    d._ok()
    assert doc.well.intervals == [] and "different" in no_modal_boxes[-1][1][2]
    d._cell(0, COL_BASE, QLineEdit).setText("7855,5")
    d._ok()
    assert doc.well.intervals == [Interval(7800, 7855.5, "perforation", "")]


# ---------------------------------------------------------------- synchronized cursor


def test_cursor_is_shown_in_every_correlated_well(testdata_well, samples, qtbot):
    from innopetrol.model.well import Well
    from innopetrol.ui.correlation import CorrelationWindow

    other = Well.from_las(samples / "Testdata.las")
    a = WellDocument(testdata_well, build_triple_combo(testdata_well))
    b = WellDocument(other, build_triple_combo(other))
    a.set_tops([Top("X", 7800.0)])
    b.set_tops([Top("X", 7850.0)])
    win = CorrelationWindow([a, b], "X", None, 2)
    qtbot.addWidget(win)
    win.show()
    qtbot.waitUntil(lambda: win.canvases[0].body_h > 100)
    win._apply_scale()  # flattened on X: the datum in the middle of the window
    first, second = win.canvases
    y = second.y_of(7850.0)
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication

    move = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(30, int(y)),
        QPointF(30, int(y)),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(second, move)
    assert first._cursor_y == pytest.approx(int(y))
    assert first.depth_at(first._cursor_y) == pytest.approx(7800.0, abs=1)  # the same level in the other well


# ---------------------------------------------------------------- core data


def test_core_csv_and_placement(tmp_path):
    p = tmp_path / "core.csv"
    p.write_text(
        "Depth (ft),Porosity (%),Perm [mD],Notes\n7800.1,18.5,120,ok\n7800.2,19.5,,\n7810,12,5,x\n", encoding="utf-8"
    )
    t = load_core_csv(p)
    assert list(t.columns) == ["Porosity (%)", "Perm [mD]"] and t.columns["Porosity (%)"][0] == "%"
    assert core_mnemonic("Porosity (%)") == "CORE_POROSITY"
    depth = np.arange(7790.0, 7820.0, 0.5)
    placed = place_on_grid(depth, t.depths, t.columns["Porosity (%)"][1])
    assert np.count_nonzero(np.isfinite(placed)) == 2
    assert placed[np.searchsorted(depth, 7800.0)] == pytest.approx(19.0)  # two samples averaged
    assert placed[np.searchsorted(depth, 7810.0)] == 12


def test_core_import_dialog_and_project(testdata_well, tmp_path, qtbot):
    from innopetrol.ui.core_dialog import CoreDialog

    p = tmp_path / "core.csv"
    p.write_text("Depth,Porosity (%),Grain density (g/cc)\n2380,15,2.65\n2390,22,2.66\n", encoding="utf-8")
    doc = WellDocument(testdata_well, build_triple_combo(testdata_well))
    d = CoreDialog(doc, load_core_csv(p), str(p))
    qtbot.addWidget(d)
    d.depth_unit.setCurrentIndex(d.depth_unit.findData("m"))  # core depths in meters, the log in feet
    n_tracks = len(doc.layout.tracks)
    d._ok()
    curve = doc.well.curves["CORE_POROSITY"]
    sample = np.flatnonzero(np.isfinite(curve.values))
    assert curve.values[sample].tolist() == [15.0, 22.0]
    assert doc.well.depth[sample[0]] == pytest.approx(2380 / 0.3048, abs=0.5)
    assert len(doc.layout.tracks) == n_tracks + 1 and doc.undo_stack.count() == 1
    save_project(tmp_path / "p.ipproj", [WellEntry(doc.well, doc.layout)])
    again = load_project(tmp_path / "p.ipproj").entries[0].well.curves["CORE_POROSITY"]
    assert np.array_equal(again.values, curve.values, equal_nan=True)
