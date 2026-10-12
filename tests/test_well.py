import numpy as np
import pytest

from innopetrol.model.well import Curve, Well


@pytest.mark.parametrize("name", ["CIRA3900.las", "Testdata.las", "TotalDepthPrueba.las", "pruebas.las"])
def test_load_all_samples(samples, name):
    well = Well.from_las(samples / name)
    assert well.depth.size > 100
    assert np.all(np.diff(well.depth) > 0)
    assert well.depth_unit == "ft"
    assert well.curves
    for c in well.curves.values():
        assert c.values.shape == well.depth.shape


def test_wrapped_file_and_header(testdata_well):
    w = testdata_well  # WRAP = YES
    assert w.name == "Test Well 1"
    assert w.start == 7614.0 and w.stop == 8738.0 and w.step == 0.5
    assert "SGR" in w.curves and w.curves["SGR"].unit == "GAPI"
    assert np.isnan(w.curves["SGR"].values).sum() == 2  # NULL -999 → NaN


def test_value_at_interpolates(testdata_well):
    w = testdata_well
    d0, d1 = w.depth[10], w.depth[11]
    v0, v1 = w.curves["RHOB"].values[10], w.curves["RHOB"].values[11]
    assert w.value_at("RHOB", (d0 + d1) / 2) == pytest.approx((v0 + v1) / 2)
    assert np.isnan(w.value_at("RHOB", 0))


def test_las_and_csv_roundtrip(testdata_well, tmp_path):
    w = testdata_well
    w.add_curve(Curve("TEST", "v/v", "prueba", w.curves["RHOB"].values * 2, formula="RHOB*2"))
    w.to_las(tmp_path / "out.las")
    back = Well.from_las(tmp_path / "out.las")
    assert np.allclose(back.curves["TEST"].values, w.curves["TEST"].values, equal_nan=True, atol=1e-4)
    assert back.name == w.name
    w.to_csv(tmp_path / "out.csv", mask=w.interval_mask(8000, 8100))
    lines = (tmp_path / "out.csv").read_text().splitlines()
    assert len(lines) == 1 + 200


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "cp1252"])
def test_las_encodings(samples, tmp_path, encoding):
    """Accented LAS files in UTF-8 (with and without BOM) and Windows-1252 are read without garbling."""
    import re

    text = (samples / "TotalDepthPrueba.las").read_text(encoding="latin-1")
    text, n = re.subn(r"(?m)^ *WELL *\..*$", " WELL.   Pozo Compañía Ñandú : Well Name", text, count=1)
    assert n == 1
    path = tmp_path / "acentos.las"
    path.write_text(text, encoding=encoding)
    assert Well.from_las(path).name == "Pozo Compañía Ñandú"


def test_las_export_unicode(testdata_well, tmp_path):
    w = testdata_well
    w.add_curve(Curve("PHIX", "v/v", "Porosidad φ calculada", w.curves["RHOB"].values, formula="RHOB"))
    w.to_las(tmp_path / "u.las")
    back = Well.from_las(tmp_path / "u.las")
    assert "φ" in back.curves["PHIX"].description


def test_csv_has_bom_for_excel(testdata_well, tmp_path):
    testdata_well.to_csv(tmp_path / "x.csv")
    assert (tmp_path / "x.csv").read_bytes().startswith(b"\xef\xbb\xbf")
