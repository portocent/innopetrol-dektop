"""Curve filters and depth shifting, available as calculator functions.

They are written as formulas (e.g. `despike(GR, 7, 3)`), so a filtered curve keeps how it was made and
is recomputed when a project is reopened. All of them ignore missing values (NaN) and keep the gaps.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from innopetrol.i18n import _

MAX_WINDOW = 501


def _window(n) -> int:
    """A window length: an odd whole number of samples, at least 1."""
    n = float(np.asarray(n).ravel()[0]) if np.size(n) else float("nan")
    if not np.isfinite(n) or n < 1 or n > MAX_WINDOW or n != int(n):
        raise ValueError(
            _("the window must be a whole number of samples between 1 and {maximum}").format(maximum=MAX_WINDOW)
        )
    n = int(n)
    return n if n % 2 else n + 1


def _windows(x: np.ndarray, n: int) -> np.ndarray:
    """Centered windows of n samples for every sample (the ends are padded with NaN)."""
    half = n // 2
    padded = np.concatenate((np.full(half, np.nan), np.asarray(x, float), np.full(half, np.nan)))
    return sliding_window_view(padded, n)


def smooth(x, n) -> np.ndarray:
    """Centered moving average over n samples; samples that were missing stay missing."""
    x = np.asarray(x, float)
    n = _window(n)
    w = _windows(x, n)
    valid = np.isfinite(w)
    counts = valid.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(valid, w, 0.0).sum(axis=1) / counts
    out[~np.isfinite(x)] = np.nan
    return out


def median(x, n) -> np.ndarray:
    """Centered running median over n samples (removes spikes, keeps steps sharp)."""
    x = np.asarray(x, float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # windows where every value is missing
        out = np.nanmedian(_windows(x, _window(n)), axis=1)
    out[~np.isfinite(x)] = np.nan
    return out


def despike(x, n, k=3.0) -> np.ndarray:
    """Hampel filter: a sample farther than k robust deviations from the median of its window is replaced
    by that median.

    The spread is measured in each window (the median absolute deviation, scaled to a standard deviation),
    so the normal variability of the beds is not taken for spikes. It is never smaller than the typical
    sample-to-sample change of the whole curve, so flat stretches (spread 0) do not flag tiny steps.
    """
    x = np.asarray(x, float)
    k = float(np.asarray(k).ravel()[0])
    if not np.isfinite(k) or k <= 0:
        raise ValueError(_("the threshold must be greater than zero"))
    windows = _windows(x, _window(n))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # windows where every value is missing
        med = np.nanmedian(windows, axis=1)
        spread = np.nanmedian(np.abs(windows - med[:, None]), axis=1) * 1.4826
        floor = np.nanmedian(np.abs(np.diff(x))) * 1.4826
    spread = np.fmax(spread, floor if np.isfinite(floor) else 0.0)
    with np.errstate(invalid="ignore"):
        spikes = np.abs(x - med) > k * spread
    return np.where(spikes, med, x)


def shift(x, depth, offset) -> np.ndarray:
    """The curve moved `offset` deeper (negative: shallower), e.g. to match it to another run or to core.

    Values are interpolated at the new depths; gaps stay gaps and the ends are left empty.
    """
    x, depth = np.asarray(x, float), np.asarray(depth, float)
    offset = float(np.asarray(offset).ravel()[0])
    if not np.isfinite(offset):
        raise ValueError(_("the depth offset must be a number"))
    valid = np.isfinite(x) & np.isfinite(depth)
    if valid.sum() < 2:
        return np.full(x.shape, np.nan)
    source = depth - offset  # where each new value comes from
    out = np.interp(source, depth[valid], x[valid], left=np.nan, right=np.nan)
    nearest = np.clip(np.searchsorted(depth, source), 0, depth.size - 1)
    out[~valid[nearest]] = np.nan  # do not bridge gaps
    return out


FILTERS: dict[str, Callable[..., np.ndarray]] = {"smooth": smooth, "median": median, "despike": despike, "shift": shift}
