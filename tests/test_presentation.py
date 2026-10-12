"""Presentation: backup (wrap) scales, fills colored by value, volumes track, log heading, picking tops."""

import numpy as np
import pytest
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter

from innopetrol.model import petro
from innopetrol.model.layout import CurveStyle, FillSpec, LogLayout, TrackSpec
from innopetrol.model.mnemonics import build_triple_combo, build_volumes_track
from innopetrol.model.tops import Top
from innopetrol.model.well import Curve, Well
from innopetrol.render.colormaps import palette
from innopetrol.render.painter import DepthTransform, backup_scale, draw_track_body

W, H = 150, 100


def synthetic(**curves) -> Well:
    depth = np.arange(0.0, 100.0, 0.5)
    return Well(
        "S", None, depth, "m", curves={m: Curve(m, u, "", np.asarray(v, float)) for m, (u, v) in curves.items()}
    )


def render(track: TrackSpec, well) -> QImage:
    img = QImage(W, H, QImage.Format.Format_RGB32)
    img.fill(Qt.GlobalColor.white)
    p = QPainter(img)
    draw_track_body(p, QRectF(0, 0, W, H), track, well, DepthTransform(0, 1.0))
    p.end()
    return img


def color_at(img, x, y) -> QColor:
    return QColor(img.pixel(int(x), int(y)))


def is_close(c: QColor, ref: QColor, tol=40) -> bool:
    return abs(c.red() - ref.red()) + abs(c.green() - ref.green()) + abs(c.blue() - ref.blue()) <= tol


def test_wrapped_curve_is_drawn_again_one_scale_width_to_the_left(qapp):
    well = synthetic(GR=("GAPI", np.full(200, 100.0)))  # beyond a 0–75 scale
    style = CurveStyle("GR", color="#ff0000", left=0, right=75, width=3)
    plain = render(TrackSpec(grid="none", curves=[style]), well)
    style.wrap = True
    wrapped = render(TrackSpec(grid="none", curves=[style]), well)
    x = 100 / 75 * W - W  # 50 px: where 100 falls on the backup scale 75–150

    def reddish(c: QColor) -> bool:  # dense dashed curves are drawn semi-transparent
        return c.red() > 200 and c.green() < 180 and c.blue() < 180

    assert not any(reddish(color_at(plain, x, y)) for y in range(10, 90))
    assert sum(reddish(color_at(wrapped, x, y)) for y in range(10, 90)) > 60


def test_backup_scales():
    assert backup_scale(CurveStyle("GR", left=0, right=150)) == (150, 300)
    assert backup_scale(CurveStyle("ILD", left=0.2, right=2000, log=True)) == pytest.approx((2000, 2e7))


def test_fill_colored_by_value(qapp):
    values = np.where(np.arange(200) < 100, 0.0, 150.0)  # clean on top (0), shale below (150)
    well = synthetic(GR=("GAPI", values))
    track = TrackSpec(
        grid="none",
        curves=[CurveStyle("GR", left=0, right=150, visible=False)],
        fills=[FillSpec(left_curve="GR", colormap="gamma_ray")],
    )
    colors = palette("gamma_ray")
    img = render(track, well)  # from the curve to the right edge
    assert is_close(color_at(img, W / 2, 23), colors[0])  # GR 0: first color
    track.fills = [FillSpec(right_curve="GR", colormap="gamma_ray")]  # from the left edge to the curve
    img = render(track, well)
    assert is_close(color_at(img, W / 2, 75), colors[-1])  # shale: last color
    assert is_close(color_at(img, W / 2, 23), QColor(Qt.GlobalColor.white))  # GR 0: nothing to fill


def test_volumes_track_stacks_fractions(qapp):
    n = 200
    well = synthetic(
        VSH=("v/v", np.full(n, 0.3)),
        VMAT=("v/v", np.full(n, 0.5)),
        BVH=("v/v", np.full(n, 0.1)),
        BVW=("%", np.full(n, 10.0)),
    )  # water in percent
    track = build_volumes_track(well)
    assert [c.mnemonic for c in track.curves] == ["VSH", "VMAT", "BVH", "BVW"] and track.is_volumes
    img = render(track, well)
    for frac, style in (
        (0.15, track.curves[0]),
        (0.55, track.curves[1]),
        (0.85, track.curves[2]),
        (0.95, track.curves[3]),
    ):
        assert is_close(color_at(img, W * frac, 50), QColor(style.color), 60), style.mnemonic


def test_petrophysics_produces_volumes(testdata_well):
    curves = {
        c.mnemonic: c
        for c in petro.compute(testdata_well, petro.PetroParams(gr_curve="SGR", rhob_curve="RHOB", rt_curve="LLD"))
    }
    total = curves["VSH"].values + curves["VMAT"].values + curves["PHIE"].values
    ok = np.isfinite(total) & (curves["VMAT"].values > 0)
    assert np.allclose(total[ok], 1)
    ok = np.isfinite(curves["SW"].values)
    assert np.allclose((curves["BVW"].values + curves["BVH"].values)[ok], curves["PHIE"].values[ok])
    for c in curves.values():
        testdata_well.add_curve(c)
    layout = build_triple_combo(testdata_well)
    kinds = [t.kind for t in layout.tracks]
    assert kinds.count("volumes") == 1
    assert not any(c.mnemonic in ("VMAT", "BVW") for t in layout.tracks if not t.is_volumes for c in t.curves)


def test_layout_round_trip_keeps_new_fields():
    layout = LogLayout(
        [
            TrackSpec(
                kind="volumes",
                curves=[CurveStyle("GR", wrap=True)],
                fills=[FillSpec(left_curve="GR", colormap="viridis")],
            )
        ]
    )
    assert LogLayout.from_dict(layout.to_dict()) == layout


def test_heading_and_pdf_pages(testdata_well, tmp_path, qapp):
    from innopetrol.model.survey import Survey
    from innopetrol.render.export import export_pdf, export_png, heading_rows

    w = testdata_well
    w.elevation = 85.0
    w.survey = Survey(np.array([0.0, 8000]), np.array([0.0, 20]), np.array([0.0, 90]))
    rows = dict(heading_rows(w, 500, 7600, 8700))
    assert rows["Company"] == "PGL" and rows["Field"] == "Somewhere"
    assert "85" in rows["Elevation of the depth reference"] and "20.0°" in rows["Deviation survey"]
    layout = build_triple_combo(w)
    with_heading = export_pdf(tmp_path / "a.pdf", w, layout, 200, 7000, 8700, dpi=100)
    without = export_pdf(tmp_path / "b.pdf", w, layout, 200, 7000, 8700, dpi=100, heading=False)
    assert with_heading >= without >= 2
    export_png(tmp_path / "a.png", w, layout, 1000, 7600, 7700, dpi=72)
    assert QImage(str(tmp_path / "a.png")).height() > QImage(str(tmp_path / "a.png")).width() / 10


def test_track_editor_keeps_wrap_and_colormap(qtbot, testdata_well):
    from PySide6.QtWidgets import QCheckBox

    from innopetrol.ui.document import WellDocument
    from innopetrol.ui.track_editor import C_WRAP, F_COLORMAP, TrackEditor

    doc = WellDocument(testdata_well, build_triple_combo(testdata_well))
    ed = TrackEditor(doc, 0)
    qtbot.addWidget(ed)
    ed.curve_table.cellWidget(0, C_WRAP).findChild(QCheckBox).setChecked(True)
    combo = ed.fill_table.cellWidget(0, F_COLORMAP)
    combo.setCurrentIndex(combo.findData("gamma_ray"))
    assert ed._apply()
    assert doc.layout.tracks[0].curves[0].wrap and doc.layout.tracks[0].fills[0].colormap == "gamma_ray"


@pytest.fixture
def correlation(qtbot, samples, testdata_well):
    from innopetrol.ui.correlation import CorrelationWindow
    from innopetrol.ui.document import WellDocument

    a = WellDocument(testdata_well, build_triple_combo(testdata_well))
    other = Well.from_las(samples / "TotalDepthPrueba.las")
    b = WellDocument(other, build_triple_combo(other))
    a.set_tops([Top("Sand A", 7800.0, "#123456")])
    win = CorrelationWindow([a, b], "__depth__", None, 2)
    qtbot.addWidget(win)
    win.show()
    qtbot.waitUntil(lambda: win.canvases[0].body_h > 100)
    return win, a, b


def test_pick_tops_in_correlation(correlation, qtbot):
    win, a, b = correlation
    assert win.top_name.findText("Sand A") >= 0
    win.top_name.setEditText("Sand A")
    win.pick.setChecked(True)
    canvas = win.canvases[1]
    y = canvas.header_h + 100
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPointF(40, y).toPoint())
    top = next(t for t in b.well.tops if t.name == "Sand A")
    assert top.depth == pytest.approx(canvas.depth_at(y), abs=0.5)
    assert top.color == "#123456"  # same name, same color in every well
    win.place_top(0, 7900.0, "Sand A")  # moving an existing top
    assert [t.depth for t in a.well.tops] == [7900.0]
    win.undo_pick()
    assert [t.depth for t in a.well.tops] == [7800.0]
    win.remove_top(1, "Sand A")
    assert b.well.tops == []
    win.undo_pick()
    assert len(b.well.tops) == 1


def test_template_never_swaps_volume_curves(testdata_well):
    from innopetrol.model.template import apply_template

    n = testdata_well.depth.size
    testdata_well.add_curve(Curve("VSH", "v/v", "", np.full(n, 0.2)))
    testdata_well.add_curve(Curve("VMAT", "v/v", "", np.full(n, 0.6)))
    testdata_well.add_curve(Curve("BVW", "v/v", "", np.full(n, 0.2)))  # no BVH in this well
    template = LogLayout(
        [
            TrackSpec(
                kind="volumes",
                curves=[
                    CurveStyle(m, family=f)
                    for m, f in (("VSH", "vsh"), ("VMAT", "matrix_volume"), ("BVH", "bvh"), ("BVW", "bvw"))
                ],
            )
        ]
    )
    result, missing = apply_template(template, testdata_well)
    assert [c.mnemonic for c in result.tracks[0].curves] == ["VSH", "VMAT", "BVW"] and missing == ["BVH"]
