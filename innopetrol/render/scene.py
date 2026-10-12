"""Composición de un registro completo: encabezados + cuerpos de todos los tracks."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFontMetricsF, QPainter

from innopetrol.model.layout import LogLayout
from innopetrol.render.painter import (DepthTransform, RenderOptions, draw_depth_body, draw_tops, draw_track_body,
                                       draw_track_header, header_height)


def track_edges(layout: LogLayout, k: float = 1.0) -> list[tuple[float, float]]:
    """(x inicial, ancho) de cada track."""
    out, x = [], 0.0
    for t in layout.tracks:
        w = t.width * k
        out.append((x, w))
        x += w
    return out


def total_width(layout: LogLayout, k: float = 1.0) -> float:
    return sum(t.width for t in layout.tracks) * k


def headers_height(p: QPainter, layout: LogLayout, k: float = 1.0) -> float:
    fm = QFontMetricsF(p.font())
    return max((header_height(t, fm, k) for t in layout.tracks), default=fm.height() * 3)


def paint_log(p: QPainter, layout: LogLayout, well, tf: DepthTransform, x0: float, y0: float,
              header_h: float, body_h: float, opts: RenderOptions, selected: int | None = None,
              draw_headers: bool = True) -> None:
    """Dibuja los tracks empezando en (x0, y0). Si draw_headers es False, el cuerpo empieza en y0."""
    body_y = y0 + (header_h if draw_headers else 0)
    first_curves = next((i for i, t in enumerate(layout.tracks) if not t.is_depth), None)
    for i, ((x, w), track) in enumerate(zip(track_edges(layout, opts.k), layout.tracks)):
        if draw_headers:
            draw_track_header(p, QRectF(x0 + x, y0, w, header_h), track, well, opts, selected == i)
        body = QRectF(x0 + x, body_y, w, body_h)
        if track.is_depth:
            draw_depth_body(p, body, well, tf, opts)
        else:
            track_opts = replace(opts, top_labels=opts.top_labels and i == first_curves)
            draw_track_body(p, body, track, well, tf, track_opts)


def paint_headers(p: QPainter, layout: LogLayout, well, x0: float, y0: float, header_h: float,
                  opts: RenderOptions, selected: int | None = None) -> None:
    for i, ((x, w), track) in enumerate(zip(track_edges(layout, opts.k), layout.tracks)):
        draw_track_header(p, QRectF(x0 + x, y0, w, header_h), track, well, opts, selected == i)


def paint_tops_overlay(p: QPainter, layout: LogLayout, well, tf: DepthTransform, x0: float, y0: float,
                       body_h: float, opts: RenderOptions) -> None:
    """Topes dibujados encima del cuerpo (la pantalla los separa de los tiles para que las
    etiquetas no queden cortadas en el borde de un tile)."""
    if not well.tops:
        return
    first_curves = next((i for i, t in enumerate(layout.tracks) if not t.is_depth), None)
    for i, (x, w) in enumerate(track_edges(layout, opts.k)):
        p.save()
        p.setClipRect(QRectF(x0 + x, y0, w, body_h))
        p.translate(x0 + x, y0)
        labels = opts.top_labels and i == first_curves
        draw_tops(p, well.tops, tf, w, body_h, opts, labels=labels)
        p.restore()
