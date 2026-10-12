import pytest
from PySide6.QtGui import QImage

from innopetrol.model.mnemonics import build_triple_combo
from innopetrol.model.tops import Top
from innopetrol.render.export import ExportError, export_pdf, export_png


@pytest.fixture
def app(qapp):
    return qapp


def test_export_png(app, testdata_well, tmp_path):
    w = testdata_well
    w.tops = [Top("Arena A", 7800)]
    out = export_png(tmp_path / "log.png", w, build_triple_combo(w), 500, 7700, 7900, dpi=120)
    img = QImage(str(out))
    assert img.width() > 500 and img.height() > 300
    # There must be colored pixels (curves/fills), not just white and gray.
    colored = sum(
        1 for x in range(0, img.width(), 7) for y in range(0, img.height(), 7) if img.pixelColor(x, y).saturation() > 80
    )
    assert colored > 50


def test_export_png_too_big(app, testdata_well, tmp_path):
    with pytest.raises(ExportError):
        export_png(
            tmp_path / "x.png",
            testdata_well,
            build_triple_combo(testdata_well),
            10,
            testdata_well.start,
            testdata_well.stop,
        )


def test_export_pdf_paginates(app, testdata_well, tmp_path):
    w = testdata_well
    pages = export_pdf(tmp_path / "log.pdf", w, build_triple_combo(w), 200, w.start, w.stop)
    data = (tmp_path / "log.pdf").read_bytes()
    assert data.startswith(b"%PDF") and pages > 1


def test_polygon_from_arrays(app):
    import numpy as np

    from innopetrol.render.painter import polygon_from_arrays

    poly = polygon_from_arrays(np.array([1.0, 2.0, 3.0]), np.array([4.0, 5.0, 6.0]))
    assert [(p.x(), p.y()) for p in poly] == [(1, 4), (2, 5), (3, 6)]
    assert polygon_from_arrays(np.array([]), np.array([])).isEmpty()
