"""Track editor: curves (scale, color, style) and fills.

Differences from the original window (addCurveWindow):
- dynamic rows (add/remove/reorder) instead of 16 fixed rows;
- every control knows which row it belongs to: no guessing with QApplication.focusWidget();
- choosing a curve proposes a scale, color and lin/log type from its family;
- validation with per-row messages and no exceptions on empty cells.
"""

from __future__ import annotations

import copy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFormLayout, QHBoxLayout, QHeaderView, QLineEdit, QMessageBox, QPushButton, QSpinBox,
                               QTableWidget, QTabWidget, QVBoxLayout, QWidget)

from innopetrol.i18n import _
from innopetrol.model.layout import CurveStyle, FillSpec, TrackSpec
from innopetrol.model.mnemonics import FAMILIES, make_curve_style
from innopetrol.model.scales import log_decades
from innopetrol.render.painter import fmt
from innopetrol.resources import app_icon
from innopetrol.ui.document import WellDocument
from innopetrol.ui.widgets import ColorButton, LineStyleCombo, PatternCombo, parse_float

C_CURVE, C_LEFT, C_RIGHT, C_LOG, C_COLOR, C_WIDTH, C_STYLE, C_VISIBLE = range(8)
F_LEFT, F_LVAL, F_RIGHT, F_RVAL, F_COLOR, F_PATTERN, F_LABEL, F_VISIBLE = range(8)
EDGE, VALUE = "__edge__", "__value__"


def _centered(w: QWidget) -> QWidget:
    box = QWidget()
    lay = QHBoxLayout(box)
    lay.addWidget(w)
    lay.setAlignment(Qt.AlignCenter)
    lay.setContentsMargins(0, 0, 0, 0)
    return box


class TrackEditor(QDialog):
    def __init__(self, doc: WellDocument, index: int, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.index = index
        self.track: TrackSpec = copy.deepcopy(doc.layout.tracks[index])
        self.setWindowTitle(f"{doc.title} — {self.track.title or _('Track {number}').format(number=index + 1)}")
        self.setWindowIcon(app_icon())
        self.resize(980, 520)

        root = QVBoxLayout(self)
        general = QFormLayout()
        self.title_edit = QLineEdit(self.track.title)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(40, 1200)
        self.width_spin.setSuffix(" px")
        self.width_spin.setValue(self.track.width)
        self.grid_combo = QComboBox()
        for key, label in (("auto", _("Automatic (from the first curve)")), ("linear", _("Linear")),
                           ("log", _("Logarithmic")), ("none", _("No grid"))):
            self.grid_combo.addItem(label, key)
        self.grid_combo.setCurrentIndex(max(self.grid_combo.findData(self.track.grid), 0))
        self.div_spin = QSpinBox()
        self.div_spin.setRange(1, 20)
        self.div_spin.setValue(self.track.divisions)
        row = QHBoxLayout()
        row.addWidget(self.width_spin)
        row.addWidget(self.grid_combo, 1)
        row.addWidget(self.div_spin)
        general.addRow(_("Title:"), self.title_edit)
        general.addRow(_("Width / grid / divisions:"), row)
        root.addLayout(general)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.curve_table = self._make_table([_("Curve"), _("Left"), _("Right"), _("Log"), _("Color"), _("Width"),
                                             _("Style"), _("Visible")])
        self.fill_table = self._make_table([_("Left bound"), _("Value"), _("Right bound"), _("Value"), _("Color"),
                                            _("Pattern"), _("Label"), _("Visible")])
        self.curve_table.horizontalHeader().setSectionResizeMode(C_CURVE, QHeaderView.Stretch)
        self.fill_table.horizontalHeader().setSectionResizeMode(F_LABEL, QHeaderView.Stretch)
        self.tabs.addTab(self._with_buttons(self.curve_table, self._add_curve, self._remove_curve, self._move_curve),
                         _("Curves"))
        self.tabs.addTab(self._with_buttons(self.fill_table, self._add_fill, self._remove_fill, self._move_fill),
                         _("Fills / shading"))
        self.tabs.currentChanged.connect(self._tab_changed)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Apply | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Apply).clicked.connect(self._apply)
        root.addWidget(buttons)

        self._fill_curves(self.track.curves)
        self._fill_fills(self.track.fills)

    # ------------------------------------------------------------------ construction

    def _make_table(self, headers):
        t = QTableWidget(0, len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setSelectionMode(QAbstractItemView.SingleSelection)
        t.verticalHeader().setDefaultSectionSize(30)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        return t

    def _with_buttons(self, table, add, remove, move):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.addWidget(table, 1)
        col = QVBoxLayout()
        for text, slot in ((_("Add"), add), (_("Remove"), remove), (_("Up"), lambda: move(-1)),
                           (_("Down"), lambda: move(1))):
            b = QPushButton(text)
            b.clicked.connect(slot)
            col.addWidget(b)
        col.addStretch()
        lay.addLayout(col)
        return w

    def _curve_names(self) -> list[str]:
        return list(self.doc.well.curves)

    # ------------------------------------------------------------------ curve table

    def _fill_curves(self, curves: list[CurveStyle]):
        self.curve_table.setRowCount(0)
        for c in curves:
            self._insert_curve_row(c)

    def _insert_curve_row(self, c: CurveStyle):
        t = self.curve_table
        r = t.rowCount()
        t.insertRow(r)
        combo = QComboBox()
        combo.addItem(_("— choose —"), None)
        for m in self._curve_names():
            curve = self.doc.well.curves[m]
            fam = FAMILIES.get(make_curve_style(self.doc.well, m).family or "")
            tip = f"{m} ({curve.unit})" + (f" — {_(fam.name)}" if fam else "")
            combo.addItem(m, m)
            combo.setItemData(combo.count() - 1, tip, Qt.ToolTipRole)
        if c.mnemonic and combo.findData(c.mnemonic) < 0:  # template curve missing from the well
            combo.addItem(_("{curve} (not available)").format(curve=c.mnemonic), c.mnemonic)
        combo.setCurrentIndex(max(combo.findData(c.mnemonic), 0))
        left = QLineEdit("" if c.left is None else fmt(c.left))
        right = QLineEdit("" if c.right is None else fmt(c.right))
        for e in (left, right):
            e.setPlaceholderText("auto")
            e.setMaximumWidth(90)
        log = QCheckBox()
        log.setChecked(c.log)
        color = ColorButton(c.color)
        width = QDoubleSpinBox()
        width.setRange(0.5, 8)
        width.setSingleStep(0.5)
        width.setValue(c.width)
        style = LineStyleCombo()
        style.set_value(c.style)
        visible = QCheckBox()
        visible.setChecked(c.visible)

        def on_curve(_index):
            m = combo.currentData()
            if not m or m not in self.doc.well.curves:
                return
            d = make_curve_style(self.doc.well, m)
            left.setText(fmt(d.left))
            right.setText(fmt(d.right))
            log.setChecked(d.log)
            color.set_color(d.color)
            style.set_value(d.style)
            width.setValue(d.width)

        combo.currentIndexChanged.connect(on_curve)
        for col, w in ((C_CURVE, combo), (C_LEFT, left), (C_RIGHT, right), (C_LOG, _centered(log)),
                       (C_COLOR, color), (C_WIDTH, width), (C_STYLE, style), (C_VISIBLE, _centered(visible))):
            t.setCellWidget(r, col, w)
        t.setCurrentCell(r, 0)

    def _read_curves(self) -> tuple[list[CurveStyle], list[str]]:
        t = self.curve_table
        out, errors = [], []
        for r in range(t.rowCount()):
            m = t.cellWidget(r, C_CURVE).currentData()
            log = t.cellWidget(r, C_LOG).findChild(QCheckBox).isChecked()
            row = _("Curves, row {row}").format(row=r + 1)
            if not m:
                errors.append(_("{row}: choose a curve").format(row=row))
                continue
            try:
                left = parse_float(t.cellWidget(r, C_LEFT).text())
                right = parse_float(t.cellWidget(r, C_RIGHT).text())
            except ValueError:
                errors.append(_("{row}: scale values must be numbers").format(row=row))
                left = right = None
            if left is not None and right is not None and left == right:
                errors.append(_("{row}: the left and right scale values cannot be equal").format(row=row))
            if log and any(v is not None and v <= 0 for v in (left, right)):
                errors.append(_("{row}: on a logarithmic scale the limits must be greater than zero").format(row=row))
            if left is None or right is None:
                d = make_curve_style(self.doc.well, m) if m in self.doc.well.curves else None
                if d is not None:
                    if log and not d.log:
                        c = self.doc.well.curves[m]
                        d.left, d.right = log_decades(c.min, c.max)
                    left = d.left if left is None else left
                    right = d.right if right is None else right
            out.append(CurveStyle(
                mnemonic=m,
                family=make_curve_style(self.doc.well, m).family if m in self.doc.well.curves else None,
                color=t.cellWidget(r, C_COLOR).color(),
                width=t.cellWidget(r, C_WIDTH).value(),
                style=t.cellWidget(r, C_STYLE).value(),
                left=left, right=right, log=log,
                visible=t.cellWidget(r, C_VISIBLE).findChild(QCheckBox).isChecked(),
            ))
        return out, errors

    def _add_curve(self):
        used = {self.curve_table.cellWidget(r, C_CURVE).currentData() for r in range(self.curve_table.rowCount())}
        free = next((m for m in self._curve_names() if m not in used), None)
        style = make_curve_style(self.doc.well, free) if free else CurveStyle(mnemonic="")
        self._insert_curve_row(style)

    def _remove_curve(self):
        r = self.curve_table.currentRow()
        if r >= 0:
            self.curve_table.removeRow(r)

    def _move_curve(self, delta):
        r = self.curve_table.currentRow()
        curves, _errors = self._read_curves()
        if r < 0 or not (0 <= r + delta < len(curves)) or len(curves) != self.curve_table.rowCount():
            return
        curves[r], curves[r + delta] = curves[r + delta], curves[r]
        self._fill_curves(curves)
        self.curve_table.setCurrentCell(r + delta, 0)

    # ------------------------------------------------------------------ fill table

    def _fill_options(self) -> list[str]:
        t = self.curve_table
        names = [t.cellWidget(r, C_CURVE).currentData() for r in range(t.rowCount())]
        return [n for n in names if n]

    def _bound_combo(self, edge_label: str, curve: str | None, value: float | None, value_edit: QLineEdit):
        combo = QComboBox()
        combo.addItem(edge_label, EDGE)
        combo.addItem(_("Fixed value…"), VALUE)
        for n in self._fill_options():
            combo.addItem(n, n)
        if curve is not None:
            if combo.findData(curve) < 0:
                combo.addItem(curve, curve)
            combo.setCurrentIndex(combo.findData(curve))
        elif value is not None:
            combo.setCurrentIndex(1)
        value_edit.setText("" if value is None else fmt(value))

        def sync(_index=None):
            is_value = combo.currentData() == VALUE
            value_edit.setEnabled(is_value)
            value_edit.setPlaceholderText(_("number") if is_value else "")

        combo.currentIndexChanged.connect(sync)
        sync()
        return combo

    def _fill_fills(self, fills: list[FillSpec]):
        self.fill_table.setRowCount(0)
        for f in fills:
            self._insert_fill_row(f)

    def _insert_fill_row(self, f: FillSpec):
        t = self.fill_table
        r = t.rowCount()
        t.insertRow(r)
        lval, rval = QLineEdit(), QLineEdit()
        for e in (lval, rval):
            e.setMaximumWidth(80)
        lcombo = self._bound_combo(_("Left edge"), f.left_curve, f.left_value, lval)
        rcombo = self._bound_combo(_("Right edge"), f.right_curve, f.right_value, rval)
        color = ColorButton(f.color)
        pattern = PatternCombo()
        pattern.set_value(f.pattern)
        label = QLineEdit(f.label)
        label.setPlaceholderText(_("(no legend)"))
        visible = QCheckBox()
        visible.setChecked(f.visible)
        for col, w in ((F_LEFT, lcombo), (F_LVAL, lval), (F_RIGHT, rcombo), (F_RVAL, rval), (F_COLOR, color),
                       (F_PATTERN, pattern), (F_LABEL, label), (F_VISIBLE, _centered(visible))):
            t.setCellWidget(r, col, w)
        t.setCurrentCell(r, 0)

    def _read_fills(self) -> tuple[list[FillSpec], list[str]]:
        t = self.fill_table
        out, errors = [], []
        for r in range(t.rowCount()):
            row = _("Fills, row {row}").format(row=r + 1)
            spec = FillSpec(color=t.cellWidget(r, F_COLOR).color(), pattern=t.cellWidget(r, F_PATTERN).value(),
                            label=t.cellWidget(r, F_LABEL).text().strip(),
                            visible=t.cellWidget(r, F_VISIBLE).findChild(QCheckBox).isChecked())
            ok = True
            for side, ccol, vcol in (("left", F_LEFT, F_LVAL), ("right", F_RIGHT, F_RVAL)):
                data = t.cellWidget(r, ccol).currentData()
                if data == VALUE:
                    try:
                        v = parse_float(t.cellWidget(r, vcol).text())
                    except ValueError:
                        v = None
                    if v is None:
                        errors.append((_("{row}: enter a number for the left bound") if side == "left" else
                                       _("{row}: enter a number for the right bound")).format(row=row))
                        ok = False
                    setattr(spec, f"{side}_value", v)
                elif data != EDGE:
                    setattr(spec, f"{side}_curve", data)
            if spec.left_curve is None and spec.right_curve is None and (spec.left_value is not None or spec.right_value is not None):
                if not self._fill_options():
                    errors.append(_("{row}: a fixed value needs at least one curve in the track to be placed").format(
                        row=row))
                    ok = False
            if spec.left_curve and spec.left_curve == spec.right_curve:
                errors.append(_("{row}: both bounds are the same curve").format(row=row))
                ok = False
            if ok:
                out.append(spec)
        return out, errors

    def _add_fill(self):
        opts = self._fill_options()
        self._insert_fill_row(FillSpec(left_curve=opts[0] if opts else None))

    def _remove_fill(self):
        r = self.fill_table.currentRow()
        if r >= 0:
            self.fill_table.removeRow(r)

    def _move_fill(self, delta):
        r = self.fill_table.currentRow()
        fills, errors = self._read_fills()
        if r < 0 or errors or not (0 <= r + delta < len(fills)):
            return
        fills[r], fills[r + delta] = fills[r + delta], fills[r]
        self._fill_fills(fills)
        self.fill_table.setCurrentCell(r + delta, 0)

    def _tab_changed(self, i):
        # The chosen curves may have changed: rebuild the fill bound options.
        if i == 1:
            fills, _errors = self._read_fills()
            self._fill_fills(fills)

    # ------------------------------------------------------------------ apply

    def _collect(self) -> TrackSpec | None:
        curves, e1 = self._read_curves()
        fills, e2 = self._read_fills()
        errors = e1 + e2
        if errors:
            QMessageBox.warning(self, _("Check the data"), "\n".join(errors))
            return None
        track = copy.deepcopy(self.track)
        track.title = self.title_edit.text().strip()
        track.width = self.width_spin.value()
        track.grid = self.grid_combo.currentData()
        track.divisions = self.div_spin.value()
        track.curves = curves
        track.fills = fills
        return track

    def _apply(self) -> bool:
        track = self._collect()
        if track is None:
            return False
        self.track = track
        self.doc.set_track(self.index, copy.deepcopy(track))
        return True

    def _ok(self):
        if self._apply():
            self.accept()
