"""DLIS reading. Test files are generated with dliswriter so no proprietary data is needed."""

import numpy as np
import pytest

from innopetrol.model import dlis
from innopetrol.model.io import load_well, load_wells

pytestmark = pytest.mark.skipif(not dlis.available(), reason="dlisio not installed on this platform")


@pytest.fixture
def dlis_file(tmp_path):
    from dliswriter import DLISFile, enums

    df = DLISFile()
    lf = df.add_logical_file()
    lf.add_origin("ORIGIN", well_name="DLIS-1", field_name="NORTE", company="ACME")
    lf.add_parameter("EKB", values={"value": [25.5], "units": "ft"})
    n = 200
    depth_ft = 5000 + np.arange(n) * 0.5
    gr = 50 + 40 * np.sin(np.arange(n) / 20)
    gr[10] = -999.25
    # Logged upwards (decreasing depth) and indexed in 0.1 in, both common in real DLIS files.
    ch_depth = lf.add_channel("TDEP", data=depth_ft[::-1] * 120, units="0.1 in")
    ch_gr = lf.add_channel("GR", data=gr[::-1], units="gAPI", long_name="Gamma Ray")
    ch_img = lf.add_channel("IMG", data=np.random.rand(n, 4))
    lf.add_frame("60B", channels=(ch_depth, ch_gr, ch_img), index_type=enums.FrameIndexType.BOREHOLE_DEPTH)
    m = 400
    ch_hr = lf.add_channel("TDEP_HR", data=1524 + np.arange(m) * 0.05, units=enums.Unit.METER)
    ch_rxo = lf.add_channel("RXO", data=np.full(m, 12.5), units="ohm")
    lf.add_frame("10B", channels=(ch_hr, ch_rxo), index_type=enums.FrameIndexType.BOREHOLE_DEPTH)
    path = tmp_path / "test.dlis"
    df.write(str(path))
    return path


def test_frames_become_wells(dlis_file):
    wells = load_wells(dlis_file)
    assert [w.source for w in wells] == ["60B", "10B"]
    main, hires = wells
    assert main.name == "DLIS-1 (60B)" and main.header_value("FLD") == "NORTE"
    assert main.depth_unit == "ft" and main.depth[0] == pytest.approx(5000) and np.all(np.diff(main.depth) > 0)
    assert np.isnan(main.curves["GR"].values[10]) and main.curves["GR"].values[0] == pytest.approx(50)
    assert any("IMG" in n for n in main.notes)  # array channel reported, not silently dropped
    assert hires.depth_unit == "m" and hires.curves["RXO"].values[0] == 12.5


def test_elevation_from_parameters(dlis_file):
    assert load_wells(dlis_file)[0].elevation == pytest.approx(25.5)


def test_load_well_by_frame(dlis_file):
    assert load_well(dlis_file, "10B").source == "10B"


def test_dlis_to_las_conversion(dlis_file, tmp_path):
    from innopetrol.model.well import Well

    w = load_well(dlis_file, "60B")
    w.to_las(tmp_path / "out.las")
    back = Well.from_las(tmp_path / "out.las")
    assert np.allclose(back.curves["GR"].values, w.curves["GR"].values, equal_nan=True, atol=1e-4)


@pytest.mark.parametrize(
    "unit,expected",
    [
        ("0.1 in", (1 / 120, "ft")),
        ("m", (1.0, "m")),
        ("ft", (1.0, "ft")),
        ("cm", (0.01, "m")),
        ("0.5 mm", (0.0005, "m")),
        ("s", None),
    ],
)
def test_depth_units(unit, expected):
    result = dlis.depth_unit_factor(unit)
    assert (
        result == expected
        if expected is None
        else (result[0] == pytest.approx(expected[0]) and result[1] == expected[1])
    )
