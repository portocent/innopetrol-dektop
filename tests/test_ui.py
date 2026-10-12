"""User interface tests in offscreen mode (no real window)."""

import math

import pytest
from PySide6.QtCore import QSettings

from innopetrol.model.tops import Top
from innopetrol.ui.main_window import MainWindow


@pytest.fixture
def win(qtbot, tmp_path, samples):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
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
    assert win.tree.topLevelItemCount() == 3  # template + 2 wells


def test_close_well_updates_tree(win, samples):
    doc = win.docs[0]
    view = win.views[doc]
    view.confirm_close = False
    view.parentWidget().close()
    assert [d.title for d in win.docs] == ["1-5"]
    texts = [win.tree.topLevelItem(i).text(0) for i in range(win.tree.topLevelItemCount())]
    assert "Test Well 1" not in texts and "1-5" in texts
    # Reopening does not overwrite the other well's item (bug in the original code)
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
    ed = track_editor.TrackEditor(win.docs[0], 2, win)  # resistivity (log)
    ed.curve_table.cellWidget(0, track_editor.C_LEFT).setText("-1")
    assert not ed._apply()
    assert "logarithmic" in warnings[0]
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
    from innopetrol.ui.petro_dialog import PetroDialog
    from innopetrol.ui.zone_summary_dialog import ZoneSummaryDialog

    doc = win.docs[0]
    doc.set_tops([Top("A", 7790), Top("B", 8040)])
    PetroDialog(doc, win)._run()
    assert {"VSH", "PHIE", "SW", "PAY_FLAG"} <= set(doc.well.curves)
    titles = [t.title for t in doc.layout.tracks]
    assert titles.index("Petrophysical results") == titles.index("Density - Neutron") + 1
    z = ZoneSummaryDialog(doc, win)
    assert [r[0] for r in z._rows] == ["(above the first top)", "A", "B"]


def test_calculator_dialog(win):
    from innopetrol.ui.calculator_dialog import CalculatorDialog

    doc = win.docs[0]
    d = CalculatorDialog(doc, win)
    d.name.setText("dphi2")
    d.expr.setPlainText("(2.65 - RHOB) / 1.65")
    d._ok()
    assert doc.well.curves["DPHI2"].formula == "(2.65 - RHOB) / 1.65"
    d = CalculatorDialog(doc, win)
    d.name.setText("RHOB")
    d.expr.setPlainText("RHOB * 2")
    d._ok()  # cannot replace an original curve
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
    StatsDialog(a, "SGR", win).show()
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
    assert math.isclose(ya, yb, abs_tol=1)  # flattened: top X ends up at the same height


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


def test_cursor_and_scroll_reuse_tiles(win, qtbot, monkeypatch):
    """Moving the cursor must not redraw curves; scrolling only draws new strips."""
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    c = win.views[win.docs[0]].canvas
    qtbot.waitExposed(c)
    c.set_scale(500)
    c.repaint()
    renders = []
    original = c._render_tile
    monkeypatch.setattr(c, "_render_tile", lambda k: renders.append(k) or original(k))
    for y in range(int(c.header_h) + 20, int(c.height()) - 20, 15):
        ev = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(80, y),
            QPointF(80, y),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        c.mouseMoveEvent(ev)
        c.repaint()
    assert renders == []
    c.scroll_by_px(30)
    c.repaint()
    assert len(renders) <= 1
    c.zoom(1.5)
    c.repaint()
    assert len(renders) > 1  # changing the scale does invalidate the cache


def test_tiles_have_no_horizontal_frame(win, qtbot):
    """Tiles must not have a top/bottom border: a line would show every 256 px."""
    from innopetrol.render.painter import BORDER

    c = win.views[win.docs[0]].canvas
    qtbot.waitExposed(c)
    c.set_scale(500)
    img = c._render_tile(30).toImage()
    x = 40  # inside the first track, away from the vertical borders
    dpr = img.devicePixelRatio()
    for row in (0, img.height() - 1):
        assert img.pixelColor(x * dpr, row).name() != BORDER.name()


def test_slow_machine_uses_previews(win, qtbot, monkeypatch):
    """If drawing is expensive, zoom shows stretched tiles and the final drawing arrives when it stops."""
    from innopetrol.ui import log_canvas

    c = win.views[win.docs[0]].canvas
    qtbot.waitExposed(c)
    c.set_scale(500)
    c.repaint()
    c._tile_ms = 50.0  # simulates a slow machine
    renders = []
    original = c._render_tile
    monkeypatch.setattr(c, "_render_tile", lambda k: renders.append(k) or original(k))
    for _ in range(5):
        c.zoom(1.1, interactive=True)
        c.repaint()
    assert c._previewing and renders == []
    qtbot.waitUntil(lambda: not c._previewing, timeout=2000)
    c.repaint()
    assert renders  # full quality once the gesture ends
    assert c.current_scale() == pytest.approx(500 / 1.1**5)

    # Border drag: guide line while dragging, width applied on release
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    c._tile_ms = 50.0
    w0 = win.docs[0].layout.tracks[0].width
    x = w0 - c.x_offset

    def ev(kind, x, buttons):
        return QMouseEvent(
            kind, QPointF(x, 300), QPointF(x, 300), Qt.MouseButton.LeftButton, buttons, Qt.KeyboardModifier.NoModifier
        )

    c.mousePressEvent(ev(QEvent.Type.MouseButtonPress, x, Qt.MouseButton.LeftButton))
    c.mouseMoveEvent(ev(QEvent.Type.MouseMove, x + 40, Qt.MouseButton.LeftButton))
    assert win.docs[0].layout.tracks[0].width == w0 and c._drag_pending == (0, w0 + 40)
    c.mouseReleaseEvent(ev(QEvent.Type.MouseButtonRelease, x + 40, Qt.MouseButton.NoButton))
    assert win.docs[0].layout.tracks[0].width == w0 + 40 and c._drag_pending is None
    assert log_canvas.FRAME_BUDGET_MS < 50


def test_zoom_buttons_and_pinch(win, qtbot):
    c = win.views[win.docs[0]].canvas
    qtbot.waitExposed(c)
    win.activate_doc(win.docs[0])
    c.set_scale(500)
    win.a_zoom_in.trigger()
    assert c.current_scale() == pytest.approx(240)
    win.a_zoom_out.trigger()
    win.a_zoom_out.trigger()
    assert c.current_scale() == pytest.approx(1000)
    win.a_fit.trigger()
    assert c.fit_mode
    # From "Fit" (non-standard scale) zooming in jumps to the nearest standard scale
    fit_scale = c.current_scale()
    win.a_zoom_in.trigger()
    assert c.current_scale() < fit_scale and round(c.current_scale()) in (
        10,
        20,
        25,
        50,
        100,
        200,
        240,
        500,
        1000,
        2000,
        5000,
    )
    # Pinch: zooms in 10 % and the depth under the fingers does not move
    c.set_scale(500)
    y = c.header_h + 200
    depth = c.depth_at(y)
    c._pinch(0.1, y)
    assert c.current_scale() == pytest.approx(500 / 1.1)
    assert c.depth_at(y) == pytest.approx(depth, abs=0.01)


def test_zoom_actions_disabled_without_wells(qtbot, tmp_path):
    from PySide6.QtCore import QSettings

    w = MainWindow(QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    qtbot.addWidget(w)
    assert not w.a_zoom_in.isEnabled() and not w.a_zoom_out.isEnabled() and not w.a_fit.isEnabled()


def test_correlation_mixes_feet_and_meters(win, qtbot, samples):
    """A well in meters next to one in feet: same physical scale and tops aligned."""
    from innopetrol.model.mnemonics import build_triple_combo
    from innopetrol.model.well import Well
    from innopetrol.ui.correlation import CorrelationWindow
    from innopetrol.ui.document import WellDocument

    feet = win.docs[0]  # Testdata.las, in feet
    metric = Well.from_las(samples / "TotalDepthPrueba.las")
    metric.depth = metric.depth * 0.3048
    metric.depth_unit = "m"
    metric_doc = WellDocument(metric, build_triple_combo(metric), parent=win)
    feet.set_tops([Top("X", 7800.0)])
    metric_doc.set_tops([Top("X", 5550.0 * 0.3048)])

    for datum in ("X", "__depth__"):
        c = CorrelationWindow([feet, metric_doc], datum, win, 2)
        c.show()
        qtbot.waitUntil(lambda c=c: c.canvases[0].body_h > 100)
        c._apply_scale()
        a, b = c.canvases
        # Same paper scale: pixels per meter must match.
        assert b.ppu == pytest.approx(a.ppu / 0.3048)
        assert a.current_scale() == pytest.approx(b.current_scale())
        if datum == "X":
            assert a.y_of(7800.0) == pytest.approx(b.y_of(5550.0 * 0.3048), abs=1)
        else:
            # Without flattening, the same true depth lines up across both wells.
            a.center_on(5600.0)
            c._propagate(a)
            assert a.y_of(5600.0) == pytest.approx(b.y_of(5600.0 * 0.3048), abs=1)
        c.close()
