"""Error log and unexpected-error reporting.

Unhandled exceptions are written to a rotating log file (with the full traceback) and reported in
a dialog instead of closing the program; the open work is autosaved first, in case the error
leaves the program unstable.
"""

from __future__ import annotations

import logging
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_NAME = "innopetrol.log"
log = logging.getLogger("innopetrol")


def setup_logging(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / LOG_NAME
    handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    return path


class ErrorReporter:
    """Replacement for sys.excepthook while the application runs."""

    def __init__(self, log_path: Path, before_report=None, show=None):
        self.log_path = log_path
        self.before_report = before_report  # e.g. autosave the open wells
        self.show = show or _show_dialog
        self._busy = False

    def install(self) -> None:
        sys.excepthook = self

    def __call__(self, exc_type, exc, tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        log.error("Unexpected error", exc_info=(exc_type, exc, tb))
        if self._busy:  # an error while reporting an error: only log it
            return
        self._busy = True
        try:
            saved = False
            if self.before_report is not None:
                try:
                    saved = bool(self.before_report())
                except Exception:  # noqa: BLE001 - the report must go on
                    log.exception("Autosave after an error failed")
            details = "".join(traceback.format_exception(exc_type, exc, tb))
            self.show(f"{exc_type.__name__}: {exc}", details, self.log_path, saved)
        finally:
            self._busy = False


def _show_dialog(message: str, details: str, log_path: Path, saved: bool) -> None:
    from PySide6.QtWidgets import QApplication, QMessageBox

    from innopetrol.i18n import _

    text = _("An unexpected error occurred. The program keeps running, but it is a good idea to save "
             "your work and restart it.")
    if saved:
        text += "\n\n" + _("Your open wells were saved for recovery.")
    box = QMessageBox(QMessageBox.Critical, _("Unexpected error"), text, QMessageBox.Ok,
                      QApplication.activeWindow())
    box.setInformativeText(_("Details were written to {path}").format(path=log_path) + "\n\n" + message)
    box.setDetailedText(details)
    box.exec()
