"""Help windows: navigation and shortcuts, and About."""

from __future__ import annotations

import sys

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QMessageBox, QWidget

from innopetrol import __version__
from innopetrol.i18n import _
from innopetrol.ui.widgets import MOD, key_text


def show_help(parent: QWidget) -> None:
    """Navigation and keyboard shortcuts (shortcuts in the platform's notation)."""
    k = key_text
    sections = [
        (
            _("Zoom"),
            [
                _(
                    "<b>−</b> and <b>+</b> buttons next to “Scale”: zoom out / in to the next standard scale "
                    "({out} / {in_})"
                ).format(out=k(QKeySequence.ZoomOut), in_=k(QKeySequence.ZoomIn)),
                _("“Fit”: whole well ({shortcut})").format(shortcut=k("Ctrl+0")),
                _("{modifier} + wheel or trackpad pinch: continuous zoom at the cursor").format(modifier=MOD),
                _("Exact scale: type 1:300 in the “Scale” field"),
            ],
        ),
        (
            _("Log"),
            [
                _("Wheel: scroll in depth · Shift + wheel: scroll horizontally · PgUp/PgDn, Home/End, arrows"),
                _("Drag a track's border: change its width · Double-click a track: edit it"),
                _("Right-click: track menu (add, move, remove, add top, scale, export)"),
            ],
        ),
        (
            _("Well tree"),
            [
                _("Double-click a curve: statistics and histogram · Double-click a top: go to that depth"),
            ],
        ),
        (
            _("Shortcuts"),
            [
                _(
                    "{open} open LAS · {save} save project · {export} export · {tsave} / {tload} save / load template"
                ).format(
                    open=k(QKeySequence.Open),
                    save=k(QKeySequence.Save),
                    export=k("Ctrl+E"),
                    tsave=k("Ctrl+T"),
                    tload=k("Ctrl+L"),
                ),
                _("{track} add track · {tops} tops · {petro} petrophysics · {calc} calculator").format(
                    track=k("Ctrl+Shift+T"), tops=k("Ctrl+Shift+F"), petro=k("Ctrl+P"), calc=k("Ctrl+K")
                ),
                _("{xplot} crossplot · {corr} correlation · {table} data table").format(
                    xplot=k("Ctrl+X"), corr=k("Ctrl+R"), table=k("Ctrl+D")
                ),
            ],
        ),
    ]
    html = "<br><br>".join(f"<b>{title}</b><br>" + "<br>".join(lines) for title, lines in sections)
    QMessageBox.information(parent, _("Navigation and shortcuts"), html)


def show_about(parent: QWidget) -> None:
    version = ".".join(map(str, sys.version_info[:2]))
    QMessageBox.about(
        parent,
        _("About InnoPetrol"),
        "<h3>{}</h3><p>{}</p><p>{}</p>".format(
            _("InnoPetrol — Well Viewer {version}").format(version=__version__),
            _(
                "Well log viewer and petrophysics for petroleum engineers: LAS and DLIS files, configurable "
                "tracks, MD/TVD/TVDSS, tops, petrophysics by zone, crossplots, correlation, base map and export "
                "to PDF/PNG/LAS."
            ),
            _("Original project 2020 · rewritten with Python {version} and PySide6.").format(version=version),
        )
        + "<p>{}</p><p>{}</p>".format(
            _(
                "Copyright © 2020-2026 Jacobo Porto. Free software under the GNU LGPL, version 3 or later; "
                "it comes with NO WARRANTY."
            ),
            _("Uses Qt for Python (PySide6, LGPLv3), lasio (MIT) and NumPy (BSD)."),
        ),
    )
