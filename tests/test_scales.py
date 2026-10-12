import numpy as np
import pytest

from innopetrol.model import scales


def test_map_linear_and_reversed():
    x = scales.map_values(np.array([0, 75, 150]), 0, 150, False, 300)
    assert np.allclose(x, [0, 150, 300])
    x = scales.map_values(np.array([0.45, 0.15, -0.15]), 0.45, -0.15, False, 600)
    assert np.allclose(x, [0, 300, 600])


def test_map_log():
    x = scales.map_values(np.array([0.2, 2, 20, 2000, -1, 0]), 0.2, 2000, True, 400)
    assert np.allclose(x[:4], [0, 100, 200, 400])
    assert np.isnan(x[4]) and np.isnan(x[5])


def test_nice_ranges():
    assert scales.nice_linear_range(13.88, 139.69) == (0, 150)
    assert scales.log_decades(0.47, 72.46) == (0.1, 100)


def test_log_grid():
    pos = scales.log_grid_positions(0.2, 20)
    assert pos[0] == (0.2, False)
    assert (1.0, True) in pos and (10.0, True) in pos
    assert pos[-1][0] == pytest.approx(20)


def test_physical_scale():
    # 1:1000 in meters → 1 m = 1 mm; at 25.4 dpi → 1 px per meter
    assert scales.px_per_unit(1000, 25.4, "m") == pytest.approx(1.0)
    assert scales.scale_ratio(scales.px_per_unit(500, 96, "ft"), 96, "ft") == pytest.approx(500)


def test_depth_ticks_no_float_drift():
    # Adding 0.1 steps as floats never hit 7700.0 exactly; here it always appears.
    t = scales.depth_ticks(7614.3, 8738.0, ppu=2.0)
    assert 7700.0 in t.labels or 7700.0 in t.major
    assert np.allclose(t.labels % t.label_interval, 0)
    assert t.labels.min() >= 7614.3


@pytest.mark.parametrize("current,direction,expected", [
    (500, 1, 240), (500, -1, 1000), (240, 1, 200),
    (437, 1, 240), (437, -1, 500),       # non-standard scale (wheel zoom)
    (5769, 1, 5000), (5769, -1, 5000),   # "Fit" beyond the last preset
    (10, 1, 10), (5000, -1, 5000),       # limits
])
def test_next_preset(current, direction, expected):
    assert scales.next_preset(current, direction) == expected
