"""Surface locations, trajectories and the base map."""

import numpy as np
import pytest
from PySide6.QtCore import QPointF, Qt

from innopetrol.model.location import Location, location_from_header, parse_coordinate, trajectory
from innopetrol.model.mnemonics import build_triple_combo
from innopetrol.model.project import WellEntry, load_project, save_project
from innopetrol.model.survey import Survey
from innopetrol.model.well import HeaderItem, Well


@pytest.mark.parametrize(
    "text, expected",
    [
        ("-58.4416", -58.4416),
        ("58,5 S", -58.5),
        ("58° 30' 0\" N", 58.5),
        ("N 58 30 36", 58.51),
        ("3 15 W", -3.25),
        ("12.5E", 12.5),
        ("", None),
        ("abc", None),
    ],
)
def test_parse_coordinate(text, expected):
    got = parse_coordinate(text)
    assert got == pytest.approx(expected) if expected is not None else got is None


def h(mnem, value, unit=""):
    return HeaderItem(mnem, unit, value, "")


def test_location_from_header():
    assert location_from_header([h("LATI", "58 26 29.9 N"), h("LONG", "1 53 13.6 E")]) == Location(
        pytest.approx(1.88711, abs=1e-4), pytest.approx(58.44164, abs=1e-4), True
    )
    loc = location_from_header([h("XCOORD", "1520345.5", "FT"), h("YCOORD", "640210.0", "FT")])
    assert (loc.x, loc.y, loc.geographic, loc.unit) == (1520345.5, 640210.0, False, "ft")
    assert location_from_header([h("LATI", "0"), h("LONG", "0"), h("XCOORD", ""), h("YCOORD", "")]) is None


def test_trajectory_uses_the_survey():
    survey = Survey(np.array([0.0, 1000, 2000]), np.array([0.0, 45, 45]), np.array([0.0, 90, 90]))  # east
    xs, ys = trajectory(Location(500000.0, 6000000.0), survey, "ft")
    assert xs[0] == 500000.0 and xs[-1] > 500000.0 + 0.3048 * 900 and ys[-1] == pytest.approx(6000000.0, abs=1)
    lon, lat = trajectory(Location(10.0, 60.0, True), survey, "m")
    # 1 km east at 60° N is about 0.018° of longitude.
    assert lon[-1] - 10.0 == pytest.approx(survey.east[-1] / (111320 * 0.5), rel=1e-6)
    assert lat[-1] == pytest.approx(60.0)


def test_location_is_saved_in_projects_and_undone(testdata_well, tmp_path, qapp):
    from innopetrol.ui.document import WellDocument

    w = testdata_well
    doc = WellDocument(w, build_triple_combo(w))
    doc.set_survey(None, None, Location(1.5, 58.4, True))
    save_project(tmp_path / "p.ipproj", [WellEntry(w, doc.layout)])
    assert load_project(tmp_path / "p.ipproj").entries[0].well.location == Location(1.5, 58.4, True)
    doc.undo_stack.undo()
    assert w.location is None


def located_docs(samples, qapp):
    from innopetrol.ui.document import WellDocument

    docs = []
    for name, loc in (
        ("A", Location(500000, 6000000)),
        ("B", Location(503000, 6001000)),
        ("C", None),
        ("D", Location(2.0, 58.0, True)),
    ):
        w = Well.from_las(samples / "Testdata.las")
        w.name, w.location = name, loc
        docs.append(WellDocument(w, build_triple_combo(w)))
    return docs


def test_base_map_selects_a_section(qtbot, samples, qapp):
    from innopetrol.ui.base_map import BaseMapWindow

    docs = located_docs(samples, qapp)
    win = BaseMapWindow(docs)
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    m = win.map
    m.fit()
    assert [i.doc.title for i in m.items] == ["A", "B"]  # C has no location, D another coordinate type
    sent = []
    win.correlateRequested.connect(sent.append)
    for name in ("B", "A"):
        item = next(i for i in m.items if i.doc.title == name)
        sx, sy = (float(v) for v in m.to_screen(item.location.x, item.location.y))
        qtbot.mouseClick(m, Qt.MouseButton.LeftButton, pos=QPointF(sx, sy).toPoint())
    assert win.correlate.isEnabled()
    win.correlate.click()
    assert [d.title for d in sent[0]] == ["B", "A"]  # in the order they were picked


def test_map_zoom_keeps_the_point_under_the_mouse(qtbot, samples, qapp):
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QWheelEvent

    from innopetrol.ui.base_map import BaseMapWidget, MapItem

    m = BaseMapWidget([MapItem(d) for d in located_docs(samples, qapp)[:2]], False)
    qtbot.addWidget(m)
    m.resize(600, 500)
    m.fit()
    pos = QPointF(200, 150)
    before = m.to_map(pos)
    m.wheelEvent(
        QWheelEvent(
            pos,
            pos,
            QPoint(),
            QPoint(0, 240),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
    )
    assert m.to_map(pos) == pytest.approx(before)
