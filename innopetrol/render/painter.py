"""Track drawing functions: grid, curves, fills, depth, tops and headers.

They are pure functions over a QPainter: no state and no widgets, so the same code draws
on screen, into a PNG image or into a PDF.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import shiboken6
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QTransform,
)

from innopetrol.i18n import _, pgettext
from innopetrol.model import units
from innopetrol.model.layout import CurveStyle, FillSpec, TrackSpec
from innopetrol.model.mnemonics import VOLUME_LABELS
from innopetrol.model.scales import depth_ticks, log_grid_positions, map_value, map_values
from innopetrol.render.colormaps import LEVELS, palette

PEN_STYLES = {
    "solid": Qt.SolidLine,
    "dash": Qt.DashLine,
    "dashdot": Qt.DashDotLine,
    "dot": Qt.DotLine,
    "dashdotdot": Qt.DashDotDotLine,
}
BRUSH_STYLES = {
    "solid": Qt.SolidPattern,
    "dense1": Qt.Dense1Pattern,
    "dense2": Qt.Dense2Pattern,
    "dense3": Qt.Dense3Pattern,
    "dense5": Qt.Dense5Pattern,
    "dense6": Qt.Dense6Pattern,
    "hor": Qt.HorPattern,
    "ver": Qt.VerPattern,
    "bdiag": Qt.BDiagPattern,
    "diagcross": Qt.DiagCrossPattern,
}

GRID_MINOR = QColor("#e3e6e8")
GRID_MAJOR = QColor("#b9bfc4")
GRID_STRONG = QColor("#7f8b93")
HEADER_BG = QColor("#f7f8f9")
BORDER = QColor("#2c3e50")


@dataclass
class DepthTransform:
    """Depth ↔ y mapping inside a track body."""

    top: float  # depth at y = 0
    ppu: float  # pixels per depth unit

    def y(self, depth):
        return (np.asarray(depth, dtype=float) - self.top) * self.ppu

    def depth(self, y: float) -> float:
        return self.top + y / self.ppu


@dataclass
class RenderOptions:
    k: float = 1.0  # line width factor (1 on screen, dpi/96 when exporting)
    top_labels: bool = True
    draw_tops: bool = True  # the screen draws tops separately, over the cached tiles
    dpr: float = 1.0  # physical pixels per logical pixel (2 on Retina screens)
    frame_ends: bool = True  # top/bottom border of the body (tiles have none)


def fmt(v: float | None) -> str:
    if v is None or not np.isfinite(v):
        return "—"
    if float(v).is_integer() and abs(v) < 1e7:
        return str(int(v))
    return f"{v:.4g}"


def find_style(track: TrackSpec, mnemonic: str | None) -> CurveStyle | None:
    if mnemonic is None:
        return None
    return next((c for c in track.curves if c.mnemonic == mnemonic), None)


def scale_of(style: CurveStyle) -> tuple[float, float, bool]:
    left = 0.0 if style.left is None else style.left
    right = 1.0 if style.right is None else style.right
    return left, right, style.log


def grid_mode(track: TrackSpec) -> tuple[str, CurveStyle | None]:
    visible = [c for c in track.curves if c.visible]
    if track.grid == "none":
        return "none", None
    if track.grid == "log" or (track.grid == "auto" and visible and visible[0].log):
        ref = next((c for c in visible if c.log), None)
        return "log", ref
    return "linear", None


# ------------------------------------------------------------------------------ track body


def visible_slice(depth: np.ndarray, tf: DepthTransform, height: float, margin: float = 8) -> slice:
    """Samples within the visible height (plus a margin so nothing is cut at the edges)."""
    d0, d1 = tf.depth(-margin), tf.depth(height + margin)
    i0 = max(int(np.searchsorted(depth, d0)) - 1, 0)
    i1 = min(int(np.searchsorted(depth, d1)) + 1, depth.size)
    return slice(i0, i1)


def draw_track_body(
    p: QPainter, rect: QRectF, track: TrackSpec, well, tf: DepthTransform, opts: RenderOptions = RenderOptions()
) -> None:
    p.save()
    p.setClipRect(rect)
    p.translate(rect.topLeft())
    w, h = rect.width(), rect.height()
    p.fillRect(QRectF(0, 0, w, h), Qt.white)

    _draw_vertical_grid(p, track, w, h, opts)
    _draw_depth_lines(p, tf, w, h, opts)
    sl = visible_slice(well.depth, tf, h)
    if sl.stop > sl.start and track.is_volumes:
        _draw_volumes(p, track, well, sl, tf.y(well.depth[sl]), w, opts)
    elif sl.stop > sl.start:
        y = tf.y(well.depth[sl])
        for fill in track.fills:
            if fill.visible:
                _draw_fill(p, track, fill, well, sl, y, w, opts)
        for style in track.curves:
            if style.visible and style.mnemonic in well.curves:
                _draw_curve(p, style, well.curves[style.mnemonic].values[sl], y, w, h, opts)
    if opts.draw_tops:
        draw_tops(p, well.tops, tf, w, h, opts, labels=opts.top_labels)

    _draw_frame(p, w, h, opts)
    p.restore()


def _draw_frame(p, w, h, opts):
    p.setPen(QPen(BORDER, 1.2 * opts.k))
    p.setBrush(Qt.NoBrush)
    if opts.frame_ends:
        p.drawRect(QRectF(0, 0, w, h))
    else:
        p.drawLine(QPointF(0, 0), QPointF(0, h))
        p.drawLine(QPointF(w, 0), QPointF(w, h))


def _draw_vertical_grid(p, track, w, h, opts):
    mode, ref = grid_mode(track)
    if mode == "none":
        return
    if mode == "log" and ref is not None:
        left, right, _log = scale_of(ref)
        for value, decade in log_grid_positions(left, right):
            x = map_value(value, left, right, True, w)
            p.setPen(QPen(GRID_STRONG if decade else GRID_MAJOR, (1.0 if decade else 0.6) * opts.k))
            p.drawLine(QPointF(x, 0), QPointF(x, h))
        return
    n = max(track.divisions, 1)
    for i in range(1, n):
        x = w * i / n
        strong = n % 2 == 0 and i == n // 2
        p.setPen(QPen(GRID_STRONG if strong else GRID_MAJOR, (1.0 if strong else 0.6) * opts.k))
        p.drawLine(QPointF(x, 0), QPointF(x, h))


def _draw_depth_lines(p, tf, w, h, opts):
    ticks = depth_ticks(tf.depth(-2), tf.depth(h + 2), tf.ppu / opts.k)
    for values, color, width in (
        (ticks.minor, GRID_MINOR, 0.6),
        (ticks.major, GRID_MAJOR, 0.8),
        (ticks.labels, GRID_STRONG, 1.0),
    ):
        p.setPen(QPen(color, width * opts.k))
        _hlines(p, tf.y(values), 0, w)


def _qpolygon(n: int) -> tuple[QPolygonF, np.ndarray]:
    """A QPolygonF of n points plus a numpy (n, 2) view over its memory.

    Writing into the view fills the polygon without creating one QPointF object per point,
    which was the slow part of converting thousands of samples.
    """
    poly = QPolygonF()
    if n == 0:  # no points, no memory to write into
        return poly, np.empty((0, 2))
    poly.resize(n)
    # The shiboken6 stub only declares VoidPtr(address); the size and writable arguments exist at runtime.
    memory = shiboken6.VoidPtr(poly.data(), n * 16, True)  # type: ignore[call-arg]
    view = np.frombuffer(memory, dtype=np.float64).reshape(n, 2)
    return poly, view


def polygon_from_arrays(x: np.ndarray, y: np.ndarray) -> QPolygonF:
    poly, view = _qpolygon(x.size)
    view[:, 0] = x
    view[:, 1] = y
    return poly


def _hlines(p: QPainter, ys: np.ndarray, x0, x1) -> None:
    """Horizontal lines in a single call (x0/x1 may be scalars or arrays)."""
    n = len(ys)
    if not n:
        return
    poly, view = _qpolygon(2 * n)
    view[0::2, 0] = x0
    view[1::2, 0] = x1
    view[0::2, 1] = ys
    view[1::2, 1] = ys
    p.drawLines(poly)


def _runs(valid: np.ndarray) -> list[tuple[int, int]]:
    """Contiguous runs of True (used to break curves at data gaps)."""
    d = np.diff(np.concatenate(([0], valid.astype(np.int8), [0])))
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1), strict=True))


def _envelope(x: np.ndarray, y: np.ndarray, dpr: float):
    """Reduces a dense curve to one horizontal [min, max] span per physical pixel row.

    With several samples per pixel the zig-zag polyline covers exactly those pixels, but stroking
    it with antialiasing is very expensive. Each span includes the last value of the previous row
    so the curve stays continuous.
    """
    rows = np.floor(y * dpr).astype(np.int64)
    starts = np.flatnonzero(np.concatenate(([True], rows[1:] != rows[:-1])))
    lo = np.minimum.reduceat(x, starts)
    hi = np.maximum.reduceat(x, starts)
    last = x[np.concatenate((starts[1:], [x.size])) - 1]
    lo[1:] = np.minimum(lo[1:], last[:-1])
    hi[1:] = np.maximum(hi[1:], last[:-1])
    return lo, hi, (rows[starts] + 0.5) / dpr


WRAP_LEVELS = (-2, -1, 1, 2)  # how many scale widths a backup curve can be shifted


def wrap_style(style: str) -> str:
    """Line style of the backup (wrapped) curve: dashed, or dotted if the curve itself is dashed."""
    return "dash" if style == "solid" else "dot"


def _draw_curve(p, style: CurveStyle, values, y, w, h, opts):
    left, right, log = scale_of(style)
    raw = map_values(values, left, right, log, w)
    valid = np.isfinite(raw)
    x = np.clip(raw, 0, w)
    _stroke(p, style, style.style, x, valid, y, opts)
    if style.wrap and w > 0:
        # Values beyond an edge are drawn again shifted by whole scale widths, as on printed logs
        # (GR 150–300 over the same grid). Works on log scales too: the shift is in pixels, i.e. decades.
        with np.errstate(invalid="ignore"):
            k = np.floor(np.where(valid, raw, 0) / w)
        for j in WRAP_LEVELS:
            sel = valid & (k == j)
            if sel.any():
                _stroke(p, style, wrap_style(style.style), np.clip(raw - j * w, 0, w), sel, y, opts)


def _stroke(p, style: CurveStyle, line_style: str, x, valid, y, opts):
    color = QColor(style.color)
    width = style.width * opts.k
    r = 1.5 * opts.k + width / 2
    for a, b in _runs(valid):
        if b - a < 3:
            # Isolated samples (e.g. core data) are drawn as a visible dot.
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            for xi, yi in zip(x[a:b], y[a:b], strict=True):
                p.drawEllipse(QPointF(xi, yi), r, r)
            p.setBrush(Qt.NoBrush)
            continue
        xs, ys = x[a:b], y[a:b]
        span_rows = (ys[-1] - ys[0]) * opts.dpr
        if span_rows > 0 and (b - a) / span_rows >= 1.5:
            # Many samples per pixel row: draw the envelope as horizontal lines one physical pixel
            # tall. Dashes are indistinguishable at this density, so non-solid curves are drawn
            # semi-transparent to tell them apart.
            lo, hi, yc = _envelope(xs, ys, opts.dpr)
            span_color = QColor(color)
            if line_style != "solid":
                span_color.setAlphaF(0.45)
            pen = QPen(span_color, 1, Qt.SolidLine, Qt.FlatCap)
            pen.setCosmetic(True)
            p.setRenderHint(QPainter.Antialiasing, False)
            p.setPen(pen)
            _hlines(p, yc, lo - width / 2, hi + width / 2)
        else:
            pen = QPen(
                color,
                width,
                PEN_STYLES.get(line_style, Qt.SolidLine),
                Qt.FlatCap,
                Qt.RoundJoin if width >= 2 else Qt.MiterJoin,
            )
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setPen(pen)
            p.drawPolyline(polygon_from_arrays(xs, ys))
    p.setRenderHint(QPainter.Antialiasing, False)


def _fill_bound(track, fill: FillSpec, side: str, well, sl, w, n):
    curve = getattr(fill, f"{side}_curve")
    value = getattr(fill, f"{side}_value")
    other = getattr(fill, f"{'right' if side == 'left' else 'left'}_curve")
    if curve is not None:
        style = find_style(track, curve)
        if style is None or curve not in well.curves:
            return None
        left, right, log = scale_of(style)
        return map_values(well.curves[curve].values[sl], left, right, log, w)
    if value is not None:
        style = find_style(track, other) or next((c for c in track.curves if c.visible), None)
        if style is None:
            return None
        left, right, log = scale_of(style)
        return np.full(n, map_value(value, left, right, log, w))
    return np.full(n, 0.0 if side == "left" else w)


def _draw_fill(p, track, fill: FillSpec, well, sl, y, w, opts):
    n = y.size
    xl = _fill_bound(track, fill, "left", well, sl, w, n)
    xr = _fill_bound(track, fill, "right", well, sl, w, n)
    if xl is None or xr is None:
        return
    color_x = xl if fill.left_curve else xr if fill.right_curve else None
    xl = np.clip(xl, 0, w)
    xr = np.clip(xr, 0, w)
    if fill.colormap and color_x is not None and w > 0:
        _draw_colormap_fill(p, fill.colormap, xl, xr, np.clip(color_x / w, 0, 1), y, opts)
        return
    valid = np.isfinite(xl) & np.isfinite(xr)
    xr = np.where(valid, np.maximum(xl, xr), xr)  # only where the left bound is to the left
    path = QPainterPath()
    path.setFillRule(Qt.WindingFill)
    for a, b in _runs(valid):
        if b - a < 2:
            continue
        pts = np.concatenate((xl[a:b], xr[a:b][::-1]))
        ys = np.concatenate((y[a:b], y[a:b][::-1]))
        path.addPolygon(polygon_from_arrays(pts, ys))
    brush = QBrush(QColor(fill.color), BRUSH_STYLES.get(fill.pattern, Qt.SolidPattern))
    if opts.k != 1:
        brush.setTransform(QTransform.fromScale(opts.k, opts.k))
    p.fillPath(path, brush)


def _rows(y: np.ndarray, opts: RenderOptions):
    """Centers of the physical pixel rows covered by the samples, and the nearest sample of each."""
    dpr = opts.dpr
    r0, r1 = int(np.floor(y[0] * dpr)), int(np.ceil(y[-1] * dpr))
    if r1 <= r0 or y.size < 2:
        return None, None
    ys = (np.arange(r0, r1) + 0.5) / dpr
    idx = np.rint(np.interp(ys, y, np.arange(y.size))).astype(np.int64)
    return ys, idx


def _draw_colormap_fill(p, name: str, xl, xr, t, y, opts):
    """Fill whose color follows the value, sampled once per physical pixel row.

    Consecutive rows of the same color become one stepped polygon, so the cost is bounded by the
    height on screen (not the number of samples) and PDF viewers show no seams between rows.
    """
    ys, idx = _rows(y, opts)
    if ys is None:
        return
    a, b, tt = xl[idx], xr[idx], t[idx]
    ok = np.isfinite(a) & np.isfinite(b) & np.isfinite(tt) & (b > a)
    if not ok.any():
        return
    level = np.where(ok, np.rint(np.nan_to_num(tt) * (LEVELS - 1)), -1).astype(np.int64)
    colors = palette(name)
    half = 0.5 / opts.dpr
    starts = np.flatnonzero(np.concatenate(([True], level[1:] != level[:-1])))
    ends = np.concatenate((starts[1:], [level.size]))
    p.save()
    p.setPen(Qt.NoPen)
    p.setRenderHint(QPainter.Antialiasing, False)
    for i0, i1 in zip(starts, ends, strict=True):
        if level[i0] < 0:
            continue
        top, bottom = ys[i0:i1] - half, ys[i0:i1] + half
        # Left edge downwards and right edge upwards, two vertices per row (a staircase).
        lx = np.repeat(a[i0:i1], 2)
        ly = np.column_stack((top, bottom)).ravel()
        rx = np.repeat(b[i0:i1], 2)[::-1]
        ry = ly[::-1]
        p.setBrush(colors[level[i0]])
        p.drawPolygon(polygon_from_arrays(np.concatenate((lx, rx)), np.concatenate((ly, ry))))
    p.restore()


def volume_fractions(track: TrackSpec, well, sl) -> list[tuple[CurveStyle, np.ndarray]]:
    """Visible components of a volumes track as fractions (curves shown in % are converted)."""
    out = []
    for style in track.curves:
        if not style.visible or style.mnemonic not in well.curves:
            continue
        values = well.curves[style.mnemonic].values[sl]
        if units.normalize(style.unit) == "%":
            values = values / 100.0
        out.append((style, values))
    return out


def _draw_volumes(p, track: TrackSpec, well, sl, y, w, opts):
    """Stacked volumes from the left: each component starts where the previous one ends (0–1)."""
    parts = volume_fractions(track, well, sl)
    if not parts:
        return
    # Drawn wherever the first component (shale) is known; a missing later component counts as 0
    # (e.g. no Sw where the porosity is zero).
    valid = np.isfinite(parts[0][1])
    start = np.zeros(y.size)
    for style, values in parts:
        end = np.minimum(start + np.clip(np.nan_to_num(values), 0, 1), 1.0)
        path = QPainterPath()
        for a, b in _runs(valid):
            if b - a < 2:
                continue
            xs = np.concatenate((start[a:b], end[a:b][::-1])) * w
            path.addPolygon(polygon_from_arrays(xs, np.concatenate((y[a:b], y[a:b][::-1]))))
        p.fillPath(path, QColor(style.color))
        start = end
    # Light grid on top so values can be read through the colors.
    pen = QPen(QColor(255, 255, 255, 110), 0.6 * opts.k)
    p.setPen(pen)
    for i in range(1, 10):
        p.drawLine(QPointF(w * i / 10, y[0]), QPointF(w * i / 10, y[-1]))


def draw_tops(p, tops, tf: DepthTransform, w, h, opts: RenderOptions, labels=True):
    if not tops:
        return
    fm = QFontMetricsF(p.font())
    for top in tops:
        y = float(tf.y(top.depth))
        if y < -fm.height() or y > h + fm.height():
            continue
        color = QColor(top.color)
        p.setPen(QPen(color, 1.6 * opts.k, Qt.DashLine))
        p.drawLine(QPointF(0, y), QPointF(w, y))
        if labels:
            text = top.name
            tw = fm.horizontalAdvance(text) + 6 * opts.k
            box = QRectF(3 * opts.k, y - fm.height() - 1 * opts.k, tw, fm.height())
            p.fillRect(box, QColor(255, 255, 255, 215))
            p.setPen(color)
            p.drawText(box, Qt.AlignCenter, text)


# ------------------------------------------------------------------------------ depth track


def draw_depth_body(p: QPainter, rect: QRectF, well, tf: DepthTransform, opts: RenderOptions = RenderOptions()):
    p.save()
    p.setClipRect(rect)
    p.translate(rect.topLeft())
    w, h = rect.width(), rect.height()
    p.fillRect(QRectF(0, 0, w, h), HEADER_BG)
    font = QFont(p.font())
    margin = QFontMetricsF(font).height()  # labels split between two tiles are drawn in both
    ticks = depth_ticks(tf.depth(-margin), tf.depth(h + margin), tf.ppu / opts.k)
    p.setPen(QPen(GRID_STRONG, 0.8 * opts.k))
    for values, length in ((ticks.minor, 4), (ticks.major, 8)):
        ys = tf.y(values)
        _hlines(p, ys, 0, length * opts.k)
        _hlines(p, ys, w - length * opts.k, w)
    bold = QFont(font)
    bold.setBold(True)
    fm = QFontMetricsF(font)
    decimals = 1 if ticks.label_interval < 1 else 0
    big = ticks.label_interval * 5
    for d, y in zip(ticks.labels, tf.y(ticks.labels), strict=True):
        p.setFont(bold if abs(d / big - round(d / big)) < 1e-9 else font)
        p.setPen(BORDER)
        p.drawText(QRectF(0, y - fm.height() / 2, w, fm.height()), Qt.AlignCenter, f"{d:.{decimals}f}")
    p.setFont(font)
    if opts.draw_tops:
        draw_tops(p, well.tops, tf, w, h, opts, labels=False)
    _draw_frame(p, w, h, opts)
    p.restore()


# ------------------------------------------------------------------------------ headers


def header_height(track: TrackSpec, fm: QFontMetricsF, k: float = 1.0) -> float:
    line = fm.height()
    if track.is_depth:
        return line * 3 + 8 * k
    n_curves = sum(1 for c in track.curves if c.visible)
    if track.is_volumes:
        return line * (2 + n_curves) + (8 + 2 * n_curves) * k
    n_wraps = sum(1 for c in track.curves if c.visible and c.wrap)
    n_fills = sum(1 for f in track.fills if f.visible and f.label)
    return line * (1 + 2 * n_curves + n_wraps + n_fills) + (8 + 2 * n_curves) * k


def backup_scale(style: CurveStyle) -> tuple[float, float]:
    """Scale of the first wrap to the right: 150–300 for a 0–150 GR, 2000–200000 for 0.2–2000 ohm·m."""
    left, right, log = scale_of(style)
    return (right, right * right / left) if log else (right, right + (right - left))


def draw_track_header(
    p: QPainter, rect: QRectF, track: TrackSpec, well, opts: RenderOptions = RenderOptions(), selected: bool = False
) -> None:
    p.save()
    p.setClipRect(rect)
    p.translate(rect.topLeft())
    w, h = rect.width(), rect.height()
    p.fillRect(QRectF(0, 0, w, h), QColor("#eaf2f8") if selected else HEADER_BG)
    font = QFont(p.font())
    bold = QFont(font)
    bold.setBold(True)
    fm = QFontMetricsF(font)
    line = fm.height()
    pad = 4 * opts.k

    p.setFont(bold)
    p.setPen(BORDER)
    title = track.title or (pgettext("track title", "Depth") if track.is_depth else "")
    p.drawText(
        QRectF(pad, 2 * opts.k, w - 2 * pad, line),
        Qt.AlignCenter,
        QFontMetricsF(bold).elidedText(title, Qt.ElideRight, w - 2 * pad),
    )
    p.setFont(font)
    y = line + 4 * opts.k

    if track.is_depth:
        unit = _("feet (ft)") if well.depth_unit == "ft" else _("meters (m)")
        p.drawText(QRectF(0, y, w, line), Qt.AlignCenter, well.depth_mnemonic)
        p.drawText(QRectF(0, y + line, w, line), Qt.AlignCenter, unit)
    elif track.is_volumes:
        for style in track.curves:
            if not style.visible:
                continue
            box = QRectF(pad, y + 2 * opts.k, line * 1.6, line - 4 * opts.k)
            p.fillRect(box, QColor(style.color))
            p.setPen(QPen(QColor("#95a5a6"), 0.8 * opts.k))
            p.drawRect(box)
            curve = well.curves.get(style.mnemonic)
            label = VOLUME_LABELS.get(style.mnemonic)
            if curve is None:
                name = _("{curve} — not available").format(curve=style.mnemonic)
            else:
                name = f"{_(label)} ({style.mnemonic})" if label else style.mnemonic
            p.setPen(BORDER if curve else QColor("#999999"))
            text_x = box.right() + 4 * opts.k
            p.drawText(
                QRectF(text_x, y, w - text_x - pad, line),
                Qt.AlignLeft | Qt.AlignVCenter,
                fm.elidedText(name, Qt.ElideRight, w - text_x - pad),
            )
            y += line + 2 * opts.k
        p.setPen(BORDER)
        p.drawText(QRectF(pad, y, w, line), Qt.AlignLeft | Qt.AlignVCenter, "0")
        p.drawText(QRectF(0, y, w - pad, line), Qt.AlignRight | Qt.AlignVCenter, "1")
        p.drawText(QRectF(0, y, w, line), Qt.AlignCenter, _("volume fraction"))
    else:
        for style in track.curves:
            if not style.visible:
                continue
            color = QColor(style.color)
            curve = well.curves.get(style.mnemonic)
            name = style.mnemonic + (f" ({curve.unit})" if curve and curve.unit else "")
            if curve is None:
                name = _("{curve} — not available").format(curve=name)
                color = QColor("#999999")
            p.setPen(color)
            p.drawText(
                QRectF(pad, y, w - 2 * pad, line), Qt.AlignCenter, fm.elidedText(name, Qt.ElideRight, w - 2 * pad)
            )
            left, right, _log = scale_of(style)
            lt, rt = fmt(left), fmt(right)
            p.drawText(QRectF(pad, y + line, w, line), Qt.AlignLeft | Qt.AlignVCenter, lt)
            p.drawText(QRectF(0, y + line, w - pad, line), Qt.AlignRight | Qt.AlignVCenter, rt)
            x0 = pad + fm.horizontalAdvance(lt) + 6 * opts.k
            x1 = w - pad - fm.horizontalAdvance(rt) - 6 * opts.k
            pen = QPen(color, style.width * opts.k, PEN_STYLES.get(style.style, Qt.SolidLine))
            p.setPen(pen)
            if x1 > x0:
                p.drawLine(QPointF(x0, y + line * 1.5), QPointF(x1, y + line * 1.5))
            y += 2 * line + 2 * opts.k
            if style.wrap:
                b_left, b_right = backup_scale(style)
                p.setPen(color)
                p.drawText(
                    QRectF(pad, y - 2 * opts.k, w - 2 * pad, line),
                    Qt.AlignCenter,
                    fm.elidedText(
                        _("backup {left} – {right}").format(left=fmt(b_left), right=fmt(b_right)),
                        Qt.ElideRight,
                        w - 2 * pad,
                    ),
                )
                y += line
        for fill in track.fills:
            if not (fill.visible and fill.label):
                continue
            box = QRectF(pad, y + 1, w - 2 * pad, line - 2)
            if fill.colormap:
                gradient = QLinearGradient(box.left(), 0, box.right(), 0)
                colors = palette(fill.colormap)
                for i in range(0, LEVELS, 6):
                    gradient.setColorAt(i / (LEVELS - 1), colors[i])
                gradient.setColorAt(1.0, colors[-1])
                brush = QBrush(gradient)
            else:
                brush = QBrush(QColor(fill.color), BRUSH_STYLES.get(fill.pattern, Qt.SolidPattern))
                if opts.k != 1:
                    brush.setTransform(QTransform.fromScale(opts.k, opts.k))
            p.fillRect(box, brush)
            p.setPen(QPen(QColor("#95a5a6"), 0.8 * opts.k))
            p.drawRect(box)
            tw = fm.horizontalAdvance(fill.label) + 8 * opts.k
            label_box = QRectF(w / 2 - tw / 2, y + 1, tw, line - 2)
            p.fillRect(label_box, QColor(255, 255, 255, 220))
            p.setPen(BORDER)
            p.drawText(label_box, Qt.AlignCenter, fill.label)
            y += line

    p.setPen(QPen(BORDER, 1.2 * opts.k))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(0, 0, w, h))
    p.restore()
