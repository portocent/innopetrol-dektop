"""Funciones de dibujo de tracks: grilla, curvas, rellenos, profundidad, topes y encabezados.

Son funciones puras sobre un QPainter: no guardan estado ni dependen de widgets, por eso
la misma rutina dibuja en pantalla, en una imagen PNG o en un PDF.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QPolygonF, QTransform

from innopetrol.model.layout import CurveStyle, FillSpec, TrackSpec
from innopetrol.model.scales import depth_ticks, log_grid_positions, map_values

PEN_STYLES = {
    "solid": Qt.SolidLine, "dash": Qt.DashLine, "dashdot": Qt.DashDotLine,
    "dot": Qt.DotLine, "dashdotdot": Qt.DashDotDotLine,
}
BRUSH_STYLES = {
    "solid": Qt.SolidPattern, "dense1": Qt.Dense1Pattern, "dense2": Qt.Dense2Pattern,
    "dense3": Qt.Dense3Pattern, "dense5": Qt.Dense5Pattern, "dense6": Qt.Dense6Pattern,
    "hor": Qt.HorPattern, "ver": Qt.VerPattern, "bdiag": Qt.BDiagPattern, "diagcross": Qt.DiagCrossPattern,
}

GRID_MINOR = QColor("#e3e6e8")
GRID_MAJOR = QColor("#b9bfc4")
GRID_STRONG = QColor("#7f8b93")
HEADER_BG = QColor("#f7f8f9")
BORDER = QColor("#2c3e50")


@dataclass
class DepthTransform:
    """Relación profundidad ↔ y dentro del cuerpo de un track."""

    top: float  # profundidad en y = 0
    ppu: float  # píxeles por unidad de profundidad

    def y(self, depth):
        return (np.asarray(depth, dtype=float) - self.top) * self.ppu

    def depth(self, y: float) -> float:
        return self.top + y / self.ppu


@dataclass
class RenderOptions:
    k: float = 1.0  # factor para grosores (1 en pantalla, dpi/96 al exportar)
    top_labels: bool = True


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


# ------------------------------------------------------------------------------ cuerpo de track


def visible_slice(depth: np.ndarray, tf: DepthTransform, height: float) -> slice:
    d0, d1 = tf.depth(0), tf.depth(height)
    i0 = max(int(np.searchsorted(depth, d0)) - 1, 0)
    i1 = min(int(np.searchsorted(depth, d1)) + 1, depth.size)
    return slice(i0, i1)


def draw_track_body(p: QPainter, rect: QRectF, track: TrackSpec, well, tf: DepthTransform,
                    opts: RenderOptions = RenderOptions()) -> None:
    p.save()
    p.setClipRect(rect)
    p.translate(rect.topLeft())
    w, h = rect.width(), rect.height()
    p.fillRect(QRectF(0, 0, w, h), Qt.white)

    _draw_vertical_grid(p, track, w, h, opts)
    _draw_depth_lines(p, tf, w, h, opts)
    sl = visible_slice(well.depth, tf, h)
    if sl.stop > sl.start:
        y = tf.y(well.depth[sl])
        for fill in track.fills:
            if fill.visible:
                _draw_fill(p, track, fill, well, sl, y, w, opts)
        for style in track.curves:
            if style.visible and style.mnemonic in well.curves:
                _draw_curve(p, style, well.curves[style.mnemonic].values[sl], y, w, h, opts)
    draw_tops(p, well.tops, tf, w, h, opts, labels=opts.top_labels)

    p.setPen(QPen(BORDER, 1.2 * opts.k))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(0, 0, w, h))
    p.restore()


def _draw_vertical_grid(p, track, w, h, opts):
    mode, ref = grid_mode(track)
    if mode == "none":
        return
    if mode == "log" and ref is not None:
        left, right, _ = scale_of(ref)
        for value, decade in log_grid_positions(left, right):
            x = float(map_values(np.array([value]), left, right, True, w)[0])
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
    ticks = depth_ticks(tf.depth(0), tf.depth(h), tf.ppu * 1 / opts.k)
    for values, color, width in ((ticks.minor, GRID_MINOR, 0.6), (ticks.major, GRID_MAJOR, 0.8),
                                 (ticks.labels, GRID_STRONG, 1.0)):
        p.setPen(QPen(color, width * opts.k))
        for y in tf.y(values):
            p.drawLine(QPointF(0, y), QPointF(w, y))


def _runs(valid: np.ndarray) -> list[tuple[int, int]]:
    """Tramos continuos de True (para cortar las curvas en los huecos de datos)."""
    d = np.diff(np.concatenate(([0], valid.astype(np.int8), [0])))
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))


def _decimate(x: np.ndarray, y: np.ndarray, max_points: int) -> tuple[np.ndarray, np.ndarray]:
    """Si hay muchas más muestras que píxeles, conserva el mínimo y máximo de cada grupo."""
    k = int(np.ceil(x.size / max_points))
    if k <= 2:
        return x, y
    n = (x.size // k) * k
    xs = x[:n].reshape(-1, k)
    ys = y[:n].reshape(-1, k)
    out_x = np.empty(xs.shape[0] * 2)
    out_y = np.empty(xs.shape[0] * 2)
    out_x[0::2], out_x[1::2] = xs.min(axis=1), xs.max(axis=1)
    out_y[0::2], out_y[1::2] = ys[:, 0], ys[:, -1]
    return np.concatenate((out_x, x[n:])), np.concatenate((out_y, y[n:]))


def _polygon(x: np.ndarray, y: np.ndarray) -> QPolygonF:
    return QPolygonF([QPointF(a, b) for a, b in zip(x.tolist(), y.tolist())])


def _draw_curve(p, style: CurveStyle, values, y, w, h, opts):
    left, right, log = scale_of(style)
    x = map_values(values, left, right, log, w)
    valid = np.isfinite(x)
    np.clip(x, 0, w, out=x)
    pen = QPen(QColor(style.color), style.width * opts.k, PEN_STYLES.get(style.style, Qt.SolidLine))
    pen.setCapStyle(Qt.FlatCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setRenderHint(QPainter.Antialiasing, True)
    r = 1.5 * opts.k + style.width * opts.k / 2
    for a, b in _runs(valid):
        if b - a < 3:
            # Muestras aisladas (p. ej. datos de núcleo): se marcan con un punto visible.
            p.setBrush(QColor(style.color))
            for xi, yi in zip(x[a:b], y[a:b]):
                p.drawEllipse(QPointF(xi, yi), r, r)
            p.setBrush(Qt.NoBrush)
            continue
        xs, ys = _decimate(x[a:b], y[a:b], int(h * 2) + 2)
        p.drawPolyline(_polygon(xs, ys))
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
        return np.full(n, map_values(np.array([value]), left, right, log, w)[0])
    return np.full(n, 0.0 if side == "left" else w)


def _draw_fill(p, track, fill: FillSpec, well, sl, y, w, opts):
    n = y.size
    xl = _fill_bound(track, fill, "left", well, sl, w, n)
    xr = _fill_bound(track, fill, "right", well, sl, w, n)
    if xl is None or xr is None:
        return
    xl = np.clip(xl, 0, w)
    xr = np.clip(xr, 0, w)
    valid = np.isfinite(xl) & np.isfinite(xr)
    xr = np.where(valid, np.maximum(xl, xr), xr)  # sólo donde la izquierda está a la izquierda
    path = QPainterPath()
    path.setFillRule(Qt.WindingFill)
    for a, b in _runs(valid):
        if b - a < 2:
            continue
        pts = np.concatenate((xl[a:b], xr[a:b][::-1]))
        ys = np.concatenate((y[a:b], y[a:b][::-1]))
        path.addPolygon(_polygon(pts, ys))
    brush = QBrush(QColor(fill.color), BRUSH_STYLES.get(fill.pattern, Qt.SolidPattern))
    if opts.k != 1:
        brush.setTransform(QTransform.fromScale(opts.k, opts.k))
    p.fillPath(path, brush)


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


# ------------------------------------------------------------------------------ track de profundidad


def draw_depth_body(p: QPainter, rect: QRectF, well, tf: DepthTransform, opts: RenderOptions = RenderOptions()):
    p.save()
    p.setClipRect(rect)
    p.translate(rect.topLeft())
    w, h = rect.width(), rect.height()
    p.fillRect(QRectF(0, 0, w, h), HEADER_BG)
    ticks = depth_ticks(tf.depth(0), tf.depth(h), tf.ppu / opts.k)
    for values, length in ((ticks.minor, 4), (ticks.major, 8)):
        p.setPen(QPen(GRID_STRONG, 0.8 * opts.k))
        for y in tf.y(values):
            p.drawLine(QPointF(0, y), QPointF(length * opts.k, y))
            p.drawLine(QPointF(w - length * opts.k, y), QPointF(w, y))
    font = QFont(p.font())
    bold = QFont(font)
    bold.setBold(True)
    fm = QFontMetricsF(font)
    decimals = 1 if ticks.label_interval < 1 else 0
    big = ticks.label_interval * 5
    for d, y in zip(ticks.labels, tf.y(ticks.labels)):
        p.setFont(bold if abs(d / big - round(d / big)) < 1e-9 else font)
        p.setPen(BORDER)
        p.drawText(QRectF(0, y - fm.height() / 2, w, fm.height()), Qt.AlignCenter, f"{d:.{decimals}f}")
    p.setFont(font)
    for top in well.tops:
        y = float(tf.y(top.depth))
        if -10 <= y <= h + 10:
            p.setPen(QPen(QColor(top.color), 1.6 * opts.k, Qt.DashLine))
            p.drawLine(QPointF(0, y), QPointF(w, y))
    p.setPen(QPen(BORDER, 1.2 * opts.k))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(0, 0, w, h))
    p.restore()


# ------------------------------------------------------------------------------ encabezados


def header_height(track: TrackSpec, fm: QFontMetricsF, k: float = 1.0) -> float:
    line = fm.height()
    if track.is_depth:
        return line * 3 + 8 * k
    n_curves = sum(1 for c in track.curves if c.visible)
    n_fills = sum(1 for f in track.fills if f.visible and f.label)
    return line * (1 + 2 * n_curves + n_fills) + (8 + 2 * n_curves) * k


def draw_track_header(p: QPainter, rect: QRectF, track: TrackSpec, well, opts: RenderOptions = RenderOptions(),
                      selected: bool = False) -> None:
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
    title = track.title or ("Profundidad" if track.is_depth else "")
    p.drawText(QRectF(pad, 2 * opts.k, w - 2 * pad, line), Qt.AlignCenter,
               QFontMetricsF(bold).elidedText(title, Qt.ElideRight, w - 2 * pad))
    p.setFont(font)
    y = line + 4 * opts.k

    if track.is_depth:
        unit = "pies (ft)" if well.depth_unit == "ft" else "metros (m)"
        p.drawText(QRectF(0, y, w, line), Qt.AlignCenter, well.depth_mnemonic)
        p.drawText(QRectF(0, y + line, w, line), Qt.AlignCenter, unit)
    else:
        for style in track.curves:
            if not style.visible:
                continue
            color = QColor(style.color)
            curve = well.curves.get(style.mnemonic)
            name = style.mnemonic + (f" ({curve.unit})" if curve and curve.unit else "")
            if curve is None:
                name += " — no disponible"
                color = QColor("#999999")
            p.setPen(color)
            p.drawText(QRectF(pad, y, w - 2 * pad, line), Qt.AlignCenter,
                       fm.elidedText(name, Qt.ElideRight, w - 2 * pad))
            left, right, _ = scale_of(style)
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
        for fill in track.fills:
            if not (fill.visible and fill.label):
                continue
            box = QRectF(pad, y + 1, w - 2 * pad, line - 2)
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
