"""Dialogs that edit a well: tops, survey/elevation/location and log export."""

import numpy as np
import pytest
from PySide6.QtWidgets import QFileDialog

from innopetrol.model.location import Location
from innopetrol.model.mnemonics import build_triple_combo
from innopetrol.model.tops import Top
from innopetrol.ui.document import WellDocument


@pytest.fixture
def doc(testdata_well, qapp):
    testdata_well.tops = [Top("A", 7800.0, "#123456")]
    return WellDocument(testdata_well, build_triple_combo(testdata_well))


def test_tops_dialog_edits_and_validates(doc, qtbot, no_modal_boxes):
    from innopetrol.ui.tops_dialog import TopsDialog

    d = TopsDialog(doc)
    qtbot.addWidget(d)
    assert d.table.rowCount() == 1
    d._add()
    d.table.cellWidget(1, 0).setText("B")
    d.table.cellWidget(1, 1).setText("8100,5")  # decimal comma
    tops, errors = d._read()
    assert not errors and [(t.name, t.depth) for t in tops] == [("A", 7800.0), ("B", 8100.5)]
    d.table.cellWidget(1, 1).setText("deep")
    assert d._read()[1]  # a non-numeric depth is reported
    d.table.cellWidget(1, 1).setText("8100")
    d._ok()
    assert [t.name for t in doc.well.tops] == ["A", "B"] and doc.undo_stack.count() == 1


def test_tops_dialog_imports_csv(doc, qtbot, tmp_path, monkeypatch):
    from innopetrol.ui.tops_dialog import TopsDialog

    csv_path = tmp_path / "tops.csv"
    csv_path.write_text("pozo;nombre;profundidad\nOther;X;1\nTest Well 1;Arena;7950,5\n", encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(csv_path), "")))
    d = TopsDialog(doc)
    qtbot.addWidget(d)
    d._import()
    names = [d.table.cellWidget(r, 0).text() for r in range(d.table.rowCount())]
    assert "Arena" in names and "X" not in names  # only the rows of this well


def test_survey_dialog_sets_survey_elevation_and_location(doc, qtbot, tmp_path, monkeypatch, no_modal_boxes):
    from innopetrol.ui.survey_dialog import SurveyDialog

    survey_path = tmp_path / "s.csv"
    survey_path.write_text("MD,INC,AZI\n0,0,0\n7000,10,45\n9000,25,50\n", encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(survey_path), "")))
    d = SurveyDialog(doc)
    qtbot.addWidget(d)
    d._import()
    assert "3 stations" in d.info.text() or "stations" in d.info.text()
    d.has_elevation.setChecked(True)
    d.elevation.setValue(85.0)
    d.location_box.setChecked(True)
    d.coord_kind.setCurrentIndex(d.coord_kind.findData("geo"))
    d.coord_y.setText("58° 26' 29.9\" N")
    d.coord_x.setText("1.887")
    d._ok()
    w = doc.well
    assert w.survey is not None and w.elevation == 85.0
    assert w.location.geographic and w.location.y == pytest.approx(58.4416, abs=1e-3)
    doc.undo_stack.undo()
    assert w.survey is None and w.location is None


def test_survey_dialog_rejects_bad_coordinates(doc, qtbot, no_modal_boxes):
    from innopetrol.ui.survey_dialog import SurveyDialog

    d = SurveyDialog(doc)
    qtbot.addWidget(d)
    d.location_box.setChecked(True)
    d.coord_y.setText("95")
    d.coord_x.setText("10")
    d._ok()
    assert doc.well.location is None and no_modal_boxes  # latitude out of range: nothing saved
    d.coord_kind.setCurrentIndex(d.coord_kind.findData("m"))
    d.coord_y.setText("6000000")
    d.coord_x.setText("500000")
    assert d.location() == Location(500000.0, 6000000.0, False, "m")


@pytest.mark.parametrize("kind", ["pdf", "png"])
def test_export_dialog_writes_the_file(doc, qtbot, tmp_path, monkeypatch, no_modal_boxes, kind):
    from innopetrol.ui.export_dialog import ExportDialog

    out = tmp_path / f"log.{kind}"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(out), "")))
    d = ExportDialog(doc, (7700.0, 7900.0), 500.0)
    qtbot.addWidget(d)
    d.fmt.setCurrentIndex(d.fmt.findData(kind))
    d.interval.setCurrentIndex(1)  # what is visible on screen
    assert (d.top.value(), d.base.value()) == (7700.0, 7900.0)
    d.dpi.setValue(72)
    d._export()
    assert out.exists() and out.stat().st_size > 1000


def test_export_dialog_rejects_an_empty_interval(doc, qtbot, no_modal_boxes):
    from innopetrol.ui.export_dialog import ExportDialog

    d = ExportDialog(doc, None, None)
    qtbot.addWidget(d)
    d.top.setValue(8000)
    d.base.setValue(7900)
    d._export()
    assert no_modal_boxes and "greater" in no_modal_boxes[-1][1][2]
    assert np.isclose(d.base.maximum(), doc.view.stop)
