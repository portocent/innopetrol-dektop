"""Helpers for plots with several wells: equivalent curves, common units and zones by name."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from innopetrol.i18n import _
from innopetrol.model import units
from innopetrol.model.mnemonics import family_of, find_curve
from innopetrol.model.normalize import zone_mask as model_zone_mask
from innopetrol.model.tops import zones_from_tops

# Distinct colors for wells (categorical, colorblind-friendly first).
WELL_COLORS = [
    "#0072b2",
    "#e69f00",
    "#009e73",
    "#cc79a7",
    "#d55e00",
    "#56b4e9",
    "#7f7f7f",
    "#8c564b",
    "#bcbd22",
    "#17becf",
]


def equivalent_curve(doc, mnemonic: str) -> str | None:
    """The curve of `doc` that plays the role of `mnemonic` (same name, or same family)."""
    if mnemonic in doc.well.curves:
        return mnemonic
    family = family_of(mnemonic)
    return find_curve(doc.well, family) if family else None


def values_as(doc, mnemonic: str, ref_doc) -> np.ndarray | None:
    """Values of the equivalent curve in `doc`, in the unit `ref_doc` displays `mnemonic` in.

    None if the well has no equivalent curve. Units that cannot be converted are left as they are.
    """
    m = equivalent_curve(doc, mnemonic)
    if m is None:
        return None
    curve = doc.view.curves[m]
    target = ref_doc.view.curves[mnemonic].unit
    a, b = units.normalize(curve.unit), units.normalize(target)
    if a and b and a != b:
        try:
            return units.convert(curve.values, a, b)
        except ValueError:
            pass
    return curve.values


def zone_names(docs) -> list[str]:
    """Zone names of all the wells, in order of first appearance."""
    names: list[str] = []
    for d in docs:
        for z in zones_from_tops(d.well.tops, d.well.stop):
            if z.name not in names:
                names.append(z.name)
    return names


def zone_mask(doc, zone: str | None) -> np.ndarray:
    """Samples of a well inside the zone of that name (each well uses its own tops); None = whole well."""
    return model_zone_mask(doc.well, zone)


def well_list(docs, active) -> QListWidget:
    """Checkable list of wells (only the active one checked)."""
    lst = QListWidget()
    lst.setToolTip(
        _(
            "Wells included. Curves are matched by name or by family (e.g. GR and SGR) and "
            "converted to the units of the active well."
        )
    )
    for i, d in enumerate(docs):
        item = QListWidgetItem(d.title)
        item.setData(Qt.ItemDataRole.UserRole, d)
        item.setForeground(Qt.GlobalColor.black)
        item.setCheckState(Qt.CheckState.Checked if d is active else Qt.CheckState.Unchecked)
        item.setData(Qt.ItemDataRole.DecorationRole, _swatch(WELL_COLORS[i % len(WELL_COLORS)]))
        lst.addItem(item)
    lst.setMaximumHeight(min(28 * len(docs) + 6, 160))
    return lst


def checked_docs(lst: QListWidget) -> list:
    return [
        lst.item(i).data(Qt.ItemDataRole.UserRole)
        for i in range(lst.count())
        if lst.item(i).checkState() == Qt.CheckState.Checked
    ]


def color_of(lst: QListWidget, doc) -> str:
    for i in range(lst.count()):
        if lst.item(i).data(Qt.ItemDataRole.UserRole) is doc:
            return WELL_COLORS[i % len(WELL_COLORS)]
    return WELL_COLORS[0]


def _swatch(color: str):
    from PySide6.QtGui import QColor, QPixmap

    pm = QPixmap(12, 12)
    pm.fill(QColor(color))
    return pm
