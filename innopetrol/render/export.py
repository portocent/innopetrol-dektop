"""Exportación del registro a PNG o PDF a una escala vertical real (1:N)."""

from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QMarginsF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter

from innopetrol import __version__
from innopetrol.model.layout import LogLayout
from innopetrol.model.scales import px_per_unit
from innopetrol.render.painter import BORDER, DepthTransform, RenderOptions
from innopetrol.render.scene import headers_height, paint_log, total_width

MAX_IMAGE_PX = 32000


class ExportError(Exception):
    pass


def _title_lines(well, scale_ratio: float, top: float, bottom: float) -> list[str]:
    unit = well.depth_unit
    info = [f"Pozo: {well.name}"]
    for mnem, label in (("COMP", "Compañía"), ("FLD", "Campo"), ("UWI", "UWI"), ("LOC", "Ubicación")):
        v = well.header_value(mnem).strip()
        if v:
            info.append(f"{label}: {v}")
    return [
        "   ·   ".join(info),
        f"Escala vertical 1:{scale_ratio:g}   ·   Intervalo {top:g} – {bottom:g} {unit}   ·   InnoPetrol {__version__}",
    ]


def _draw_title(p: QPainter, rect: QRectF, lines: list[str]) -> None:
    bold = QFont(p.font())
    bold.setBold(True)
    bold.setPointSizeF(p.font().pointSizeF() * 1.25)
    p.save()
    p.setPen(BORDER)
    p.setFont(bold)
    fm_b = QFontMetricsF(bold)
    p.drawText(QRectF(rect.left(), rect.top(), rect.width(), fm_b.height()), Qt.AlignLeft | Qt.AlignVCenter, lines[0])
    p.restore()
    fm = QFontMetricsF(p.font())
    p.setPen(QColor("#566573"))
    p.drawText(QRectF(rect.left(), rect.top() + fm_b.height(), rect.width(), fm.height()),
               Qt.AlignLeft | Qt.AlignVCenter, lines[1])


def _title_height(p: QPainter) -> float:
    fm = QFontMetricsF(p.font())
    return fm.height() * 2.25 + 8


def export_png(path: str | Path, well, layout: LogLayout, scale_ratio: float, top: float, bottom: float,
               dpi: int = 200) -> Path:
    k = dpi / 96
    ppu = px_per_unit(scale_ratio, dpi, well.depth_unit)
    body_h = (bottom - top) * ppu
    margin = 12 * k
    width = int(total_width(layout, k) + 2 * margin)

    probe = QImage(1, 1, QImage.Format_ARGB32)
    _set_dpi(probe, dpi)
    with _painter(probe) as p:
        title_h = _title_height(p)
        header_h = headers_height(p, layout, k)
    height = int(title_h + header_h + body_h + 2 * margin)
    if height > MAX_IMAGE_PX:
        raise ExportError(f"la imagen tendría {height} px de alto; use PDF, un intervalo menor o una escala más chica")

    img = QImage(width, height, QImage.Format_ARGB32)
    _set_dpi(img, dpi)
    img.fill(Qt.white)
    with _painter(img) as p:
        _draw_title(p, QRectF(margin, margin, width - 2 * margin, title_h), _title_lines(well, scale_ratio, top, bottom))
        tf = DepthTransform(top, ppu)
        paint_log(p, layout, well, tf, margin, margin + title_h, header_h, body_h, RenderOptions(k=k))
    if not img.save(str(path)):
        raise ExportError("no se pudo guardar la imagen")
    return Path(path)


def export_pdf(path: str | Path, well, layout: LogLayout, scale_ratio: float, top: float, bottom: float,
               dpi: int = 300, page: str = "A4") -> int:
    """PDF paginado. El ancho de página se ajusta a los tracks; el encabezado se repite en cada hoja."""
    k = dpi / 96
    ppu = px_per_unit(scale_ratio, dpi, well.depth_unit)
    margin_mm = 10
    track_w_mm = total_width(layout, k) / dpi * 25.4
    base = QPageSize(QPageSize.A3 if page == "A3" else QPageSize.Letter if page == "Letter" else QPageSize.A4)
    base_mm = base.size(QPageSize.Millimeter)
    page_w = max(base_mm.width(), track_w_mm + 2 * margin_mm)
    page_size = QPageSize(QSizeF(page_w, base_mm.height()), QPageSize.Millimeter, "InnoPetrol")

    writer = QPdfWriter(str(path))
    writer.setResolution(dpi)
    writer.setPageLayout(QPageLayout(page_size, QPageLayout.Portrait, QMarginsF(margin_mm, margin_mm, margin_mm, margin_mm),
                                     QPageLayout.Millimeter))
    writer.setTitle(f"{well.name} - registro 1:{scale_ratio:g}")
    writer.setCreator(f"InnoPetrol {__version__}")

    pages = 0
    with _painter(writer) as p:
        p.setFont(QFont(p.font().family(), 8))
        area = writer.pageLayout().paintRectPixels(dpi)
        title_h = _title_height(p)
        header_h = headers_height(p, layout, k)
        body_h = area.height() - title_h - header_h
        if body_h <= 50:
            raise ExportError("demasiadas curvas para el alto de la página")
        depth_per_page = body_h / ppu
        n_pages = max(1, math.ceil((bottom - top) / depth_per_page - 1e-9))
        lines = _title_lines(well, scale_ratio, top, bottom)
        for i in range(n_pages):
            if i:
                writer.newPage()
            d0 = top + i * depth_per_page
            d1 = min(bottom, d0 + depth_per_page)
            h = (d1 - d0) * ppu
            _draw_title(p, QRectF(0, 0, area.width(), title_h), [lines[0], lines[1] + f"   ·   Hoja {i + 1}/{n_pages}"])
            paint_log(p, layout, well, DepthTransform(d0, ppu), 0, title_h, header_h, h, RenderOptions(k=k))
            pages += 1
    return pages


def _set_dpi(img: QImage, dpi: float) -> None:
    dpm = round(dpi / 0.0254)
    img.setDotsPerMeterX(dpm)
    img.setDotsPerMeterY(dpm)


class _painter:
    """QPainter como context manager: garantiza p.end() aunque haya una excepción."""

    def __init__(self, device):
        self.device = device

    def __enter__(self) -> QPainter:
        self.p = QPainter(self.device)
        self.p.setRenderHint(QPainter.TextAntialiasing)
        return self.p

    def __exit__(self, *exc):
        self.p.end()
        return False



