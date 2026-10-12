"""Export of the log to PNG or PDF at a true vertical scale (1:N)."""

from __future__ import annotations

import datetime
import math
from pathlib import Path

from PySide6.QtCore import QMarginsF, QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen

from innopetrol import __version__
from innopetrol.i18n import N_, _
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
    reference = getattr(well, "reference", "md").upper()  # MD, TVD or TVDSS when drawing a DepthView
    interval = _("Interval {reference} {top} – {bottom} {unit}").format(
        reference=reference, top=f"{top:g}", bottom=f"{bottom:g}", unit=unit)
    return ["   ·   ".join(info), f"{scale}   ·   {interval}   ·   InnoPetrol {__version__}"]


# Header items shown in the log heading, in this order (mnemonic, label translated when shown).
HEADING_ITEMS = (("COMP", N_("Company")), ("FLD", N_("Field")), ("LOC", N_("Location")), ("CTRY", N_("Country")),
                 ("STAT", N_("State / province")), ("PROV", N_("State / province")), ("CNTY", N_("County")),
                 ("UWI", "UWI"), ("API", "API"), ("LIC", N_("Licence")), ("SRVC", N_("Service company")),
                 ("DATE", N_("Log date")))


def heading_rows(well, scale_ratio: float, top: float, bottom: float) -> list[tuple[str, str]]:
    """(label, value) pairs of the log heading: well data from the file plus how the log is drawn."""
    stored = getattr(well, "well", well)  # the Well behind a DepthView
    rows: list[tuple[str, str]] = []
    seen = set()
    for mnem, label in HEADING_ITEMS:
        value = well.header_value(mnem).strip()
        if value and _(label) not in seen:
            rows.append((_(label), value))
            seen.add(_(label))
    reference = getattr(well, "reference", "md").upper()
    rows.append((_("Depth reference"), f"{reference} ({well.depth_unit})"))
    rows.append((_("Interval"), f"{top:g} – {bottom:g} {well.depth_unit}"))
    rows.append((_("Vertical scale"), f"1:{scale_ratio:g}"))
    if stored.elevation is not None:
        rows.append((_("Elevation of the depth reference"), _("{value} {unit} above sea level").format(
            value=f"{stored.elevation:g}", unit=stored.depth_unit)))
    survey = stored.survey
    rows.append((_("Deviation survey"), _("none (vertical well assumed)") if survey is None else
                 _("{count} stations, max. inclination {inc}°").format(count=survey.md.size,
                                                                     inc=f"{survey.max_inclination:.1f}")))
    if stored.path is not None:
        rows.append((_("File"), Path(stored.path).name + (f" [{stored.source}]" if stored.source else "")))
    rows.append((_("Printed"), f"{datetime.date.today().isoformat()} · InnoPetrol {__version__}"))
    return rows


def heading_height(p: QPainter, rows: list[tuple[str, str]]) -> float:
    fm = QFontMetricsF(p.font())
    return fm.height() * 2.2 + math.ceil(len(rows) / 2) * fm.height() * 1.45 + fm.height() * 0.8


def draw_heading(p: QPainter, rect: QRectF, well, rows: list[tuple[str, str]]) -> None:
    """Log heading: a framed block with the well name and a two-column grid of label/value cells."""
    base = QFont(p.font())
    bold = QFont(base)
    bold.setBold(True)
    big = QFont(bold)
    big.setPointSizeF(base.pointSizeF() * 1.6)
    line = QFontMetricsF(base).height()
    p.save()
    box = QRectF(rect.left(), rect.top(), rect.width(), rect.height() - line * 0.6)
    band = QRectF(box.left(), box.top(), box.width(), line * 2.2)
    p.fillRect(band, QColor("#eaf2f8"))
    p.setPen(BORDER)
    p.setFont(big)
    p.drawText(band.adjusted(line * 0.6, 0, -line * 0.6, 0), Qt.AlignLeft | Qt.AlignVCenter, well.name)

    half = box.width() / 2
    row_h = line * 1.45
    n = math.ceil(len(rows) / 2)
    label_w = max((QFontMetricsF(bold).horizontalAdvance(label) for label, _value in rows), default=0) + line
    label_w = min(label_w, half * 0.45)
    fm = QFontMetricsF(base)
    for i, (label, value) in enumerate(rows):
        col, r = divmod(i, n)
        cell = QRectF(box.left() + col * half, band.bottom() + r * row_h, half, row_h)
        p.setPen(QPen(QColor("#d5d8dc"), line / 14))
        p.drawLine(cell.bottomLeft(), cell.bottomRight())
        p.setPen(QColor("#566573"))
        p.setFont(bold)
        p.drawText(QRectF(cell.left() + line * 0.6, cell.top(), label_w, row_h), Qt.AlignLeft | Qt.AlignVCenter,
                   label)
        p.setPen(BORDER)
        p.setFont(base)
        vx = cell.left() + line * 0.6 + label_w
        room = cell.right() - vx - line * 0.4
        p.drawText(QRectF(vx, cell.top(), room, row_h), Qt.AlignLeft | Qt.AlignVCenter,
                   fm.elidedText(value, Qt.ElideRight, room))
    p.setPen(QPen(QColor("#d5d8dc"), line / 14))
    p.drawLine(QPointF(box.left() + half, band.bottom()), QPointF(box.left() + half, box.bottom()))
    p.setPen(QPen(BORDER, line / 10))
    p.setBrush(Qt.NoBrush)
    p.drawLine(band.bottomLeft(), band.bottomRight())
    p.drawRect(box)
    p.restore()


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
               dpi: int = 200, heading: bool = True) -> Path:
    """PNG of the interval at scale. With `heading`, the log heading (well data) replaces the title lines."""
    k = dpi / 96
    ppu = px_per_unit(scale_ratio, dpi, well.depth_unit)
    body_h = (bottom - top) * ppu
    margin = 12 * k
    width = int(total_width(layout, k) + 2 * margin)

    probe = QImage(1, 1, QImage.Format_ARGB32)
    _set_dpi(probe, dpi)
    rows = heading_rows(well, scale_ratio, top, bottom)
    with _painter(probe) as p:
        title_h = heading_height(p, rows) if heading else _title_height(p)
        header_h = headers_height(p, layout, k)
    height = int(title_h + header_h + body_h + 2 * margin)
    if height > MAX_IMAGE_PX:
        raise ExportError(_("the image would be {height} px tall; use PDF, a shorter interval or a smaller "
                            "scale").format(height=height))

    img = QImage(width, height, QImage.Format_ARGB32)
    _set_dpi(img, dpi)
    img.fill(Qt.white)
    with _painter(img) as p:
        title_rect = QRectF(margin, margin, width - 2 * margin, title_h)
        if heading:
            draw_heading(p, title_rect, well, rows)
        else:
            _draw_title(p, title_rect, _title_lines(well, scale_ratio, top, bottom))
        tf = DepthTransform(top, ppu)
        paint_log(p, layout, well, tf, margin, margin + title_h, header_h, body_h, RenderOptions(k=k))
    if not img.save(str(path)):
        raise ExportError(_("could not save the image"))
    return Path(path)


def export_pdf(path: str | Path, well, layout: LogLayout, scale_ratio: float, top: float, bottom: float,
               dpi: int = 300, page: str = "A4", heading: bool = True) -> int:
    """Paginated PDF. The page width fits the tracks; the track headers are repeated on every page.

    With `heading`, the first page starts with the log heading (well data); the others with a title line.
    """
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
        rows = heading_rows(well, scale_ratio, top, bottom)
        first_h = heading_height(p, rows) if heading else title_h
        header_h = headers_height(p, layout, k)
        body_h = area.height() - title_h - header_h
        first_body_h = area.height() - first_h - header_h
        if min(body_h, first_body_h) <= 50:
            raise ExportError(_("too many curves for the page height"))
        # Depth interval of each page: the first one is shorter when it carries the heading.
        starts = [top]
        while True:
            span = (first_body_h if len(starts) == 1 else body_h) / ppu
            if starts[-1] + span >= bottom - 1e-9:
                break
            starts.append(starts[-1] + span)
        n_pages = len(starts)
        lines = _title_lines(well, scale_ratio, top, bottom)
        for i, d0 in enumerate(starts):
            if i:
                writer.newPage()
            d1 = starts[i + 1] if i + 1 < n_pages else bottom
            h = (d1 - d0) * ppu
            page_text = _("Page {page}/{pages}").format(page=i + 1, pages=n_pages)
            if i == 0 and heading:
                draw_heading(p, QRectF(0, 0, area.width(), first_h), well, rows)
                y0 = first_h
            else:
                _draw_title(p, QRectF(0, 0, area.width(), title_h), [lines[0], lines[1] + "   ·   " + page_text])
                y0 = title_h
            paint_log(p, layout, well, DepthTransform(d0, ppu), 0, y0, header_h, h, RenderOptions(k=k))
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



