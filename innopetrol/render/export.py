"""Export of the log to PNG or PDF at a true vertical scale (1:N)."""

from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QMarginsF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter

from innopetrol import __version__
from innopetrol.i18n import _
from innopetrol.model.layout import LogLayout
from innopetrol.model.scales import px_per_unit
from innopetrol.render.painter import BORDER, DepthTransform, RenderOptions
from innopetrol.render.scene import headers_height, paint_log, total_width

MAX_IMAGE_PX = 32000


class ExportError(Exception):
    pass


def _title_lines(well, scale_ratio: float, top: float, bottom: float) -> list[str]:
    unit = well.depth_unit
    info = [_("Well: {name}").format(name=well.name)]
    for mnem, label in (("COMP", _("Company")), ("FLD", _("Field")), ("UWI", "UWI"), ("LOC", _("Location"))):
        v = well.header_value(mnem).strip()
        if v:
            info.append(f"{label}: {v}")
    scale = _("Vertical scale 1:{scale}").format(scale=f"{scale_ratio:g}")
    interval = _("Interval {top} – {bottom} {unit}").format(top=f"{top:g}", bottom=f"{bottom:g}", unit=unit)
    return ["   ·   ".join(info), f"{scale}   ·   {interval}   ·   InnoPetrol {__version__}"]


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
        raise ExportError(_("the image would be {height} px tall; use PDF, a shorter interval or a smaller "
                            "scale").format(height=height))

    img = QImage(width, height, QImage.Format_ARGB32)
    _set_dpi(img, dpi)
    img.fill(Qt.white)
    with _painter(img) as p:
        _draw_title(p, QRectF(margin, margin, width - 2 * margin, title_h), _title_lines(well, scale_ratio, top, bottom))
        tf = DepthTransform(top, ppu)
        paint_log(p, layout, well, tf, margin, margin + title_h, header_h, body_h, RenderOptions(k=k))
    if not img.save(str(path)):
        raise ExportError(_("could not save the image"))
    return Path(path)


def export_pdf(path: str | Path, well, layout: LogLayout, scale_ratio: float, top: float, bottom: float,
               dpi: int = 300, page: str = "A4") -> int:
    """Paginated PDF. The page width fits the tracks; the header is repeated on every page."""
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
    writer.setTitle(_("{well} - log 1:{scale}").format(well=well.name, scale=f"{scale_ratio:g}"))
    writer.setCreator(f"InnoPetrol {__version__}")

    pages = 0
    with _painter(writer) as p:
        p.setFont(QFont(p.font().family(), 8))
        area = writer.pageLayout().paintRectPixels(dpi)
        title_h = _title_height(p)
        header_h = headers_height(p, layout, k)
        body_h = area.height() - title_h - header_h
        if body_h <= 50:
            raise ExportError(_("too many curves for the page height"))
        depth_per_page = body_h / ppu
        n_pages = max(1, math.ceil((bottom - top) / depth_per_page - 1e-9))
        lines = _title_lines(well, scale_ratio, top, bottom)
        for i in range(n_pages):
            if i:
                writer.newPage()
            d0 = top + i * depth_per_page
            d1 = min(bottom, d0 + depth_per_page)
            h = (d1 - d0) * ppu
            _draw_title(p, QRectF(0, 0, area.width(), title_h), [lines[0], lines[1] + "   ·   " + _("Page {page}/{pages}").format(page=i + 1, pages=n_pages)])
            paint_log(p, layout, well, DepthTransform(d0, ppu), 0, title_h, header_h, h, RenderOptions(k=k))
            pages += 1
    return pages


def _set_dpi(img: QImage, dpi: float) -> None:
    dpm = round(dpi / 0.0254)
    img.setDotsPerMeterX(dpm)
    img.setDotsPerMeterY(dpm)


class _painter:
    """QPainter as a context manager: guarantees p.end() even if an exception is raised."""

    def __init__(self, device):
        self.device = device

    def __enter__(self) -> QPainter:
        self.p = QPainter(self.device)
        self.p.setRenderHint(QPainter.TextAntialiasing)
        return self.p

    def __exit__(self, *exc):
        self.p.end()
        return False



