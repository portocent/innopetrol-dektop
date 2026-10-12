"""Curve filters and depth shifting (also as calculator functions)."""

import numpy as np
import pytest

from innopetrol.model.calculator import CalculatorError, evaluate
from innopetrol.model.filters import despike, median, shift, smooth


def test_smooth_is_a_centered_average_and_keeps_gaps():
    x = np.array([0.0, 0, 3, 0, 0, np.nan, 6, 6])
    out = smooth(x, 3)
    assert out[2] == pytest.approx(1.0) and out[1] == pytest.approx(1.0)
    assert np.isnan(out[5])  # a gap stays a gap
    assert out[6] == pytest.approx(6.0)  # the missing neighbor is ignored
    assert smooth(x, 2)[2] == pytest.approx(1.0)  # even windows become odd (3)


def test_median_and_despike_remove_a_spike_but_keep_a_step():
    x = np.concatenate([np.full(20, 50.0), np.full(20, 100.0)])
    x[10] = 500.0  # spike
    m = median(x, 5)
    assert m[10] == 50.0 and m[19] == 50.0 and m[20] == 100.0  # step kept sharp
    rng = np.random.default_rng(0)
    noisy = x + rng.normal(0, 1, x.size)
    clean = despike(noisy, 5, 3)
    assert clean[10] < 60  # the spike is gone
    assert np.count_nonzero(clean != noisy) <= 3  # ordinary noise is untouched


def test_shift_moves_features_deeper_without_bridging_gaps():
    depth = np.arange(100.0, 110.0, 0.5)
    x = np.where(np.abs(depth - 104.0) < 0.1, 1.0, 0.0)
    out = shift(x, depth, 1.0)
    assert depth[np.nanargmax(out)] == pytest.approx(105.0)
    assert np.isnan(out[0]) and np.isnan(out[1])  # nothing to bring from above the top
    x[10] = np.nan
    assert np.isnan(shift(x, depth, 1.0)[12])  # the gap moved with the data


def test_as_calculator_functions():
    depth = np.arange(0.0, 10.0, 0.5)
    env = {"GR": np.linspace(0, 100, depth.size), "DEPTH": depth}
    assert np.allclose(evaluate("smooth(GR, 3)", env)[1:-1], env["GR"][1:-1])  # a line stays a line
    assert np.allclose(evaluate("shift(GR, DEPTH, 0)", env), env["GR"])
    with pytest.raises(CalculatorError, match="window"):
        evaluate("median(GR, 2.5)", env)
    with pytest.raises(CalculatorError, match="threshold"):
        evaluate("despike(GR, 5, 0)", env)


def test_despike_when_most_samples_equal_their_median():
    """Step-like curves (common in real logs) have a median absolute deviation of 0."""
    x = np.repeat([50.0, 80.0, 60.0, 90.0], 25)
    x[30] = 900.0
    out = despike(x, 5, 3)
    assert out[30] == 80.0 and np.array_equal(np.delete(out, 30), np.delete(x, 30))


def test_despike_leaves_real_logs_almost_untouched(testdata_well):
    """On a real gamma ray, only a handful of samples change, and injected spikes are removed."""
    gr = testdata_well.curves["SGR"].values.copy()
    assert np.count_nonzero(despike(gr, 7, 3) != gr) < 0.01 * gr.size
    gr[[300, 900, 1500]] = 1000.0
    out = despike(gr, 7, 3)
    assert np.all(out[[300, 900, 1500]] < 200)
