"""The work session without widgets: current project file, unsaved changes, recent files and the
autosave used to recover after a crash. The main window shows the dialogs; this class keeps the state
and does the file work, so it can be tested on its own."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths

from innopetrol.model.catalog import WellRef
from innopetrol.model.project import WellEntry, save_project
from innopetrol.ui.recovery import Recovery

MAX_RECENT = 8
log = logging.getLogger("innopetrol")


class Session:
    def __init__(self, settings: QSettings):
        self.settings = settings
        self.project_path: Path | None = None
        self.dirty = False  # changes not saved in a project file
        self.recovery = Recovery(self.data_dir / "recovery")

    @property
    def data_dir(self) -> Path:
        """Folder for the autosave and the error log. Next to the settings file when the settings are
        an .ini file (tests, portable use), otherwise the system's application data folder."""
        if self.settings.format() == QSettings.Format.IniFormat:
            return Path(self.settings.fileName()).parent
        return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))

    # ---------------------------------------------------------------- recent files
    def recent(self) -> list[str]:
        value = self.settings.value("recent") or []
        return [value] if isinstance(value, str) else list(value)

    def add_recent(self, path: str | Path) -> None:
        recent = [p for p in self.recent() if p != str(path)]
        self.settings.setValue("recent", [str(path), *recent][:MAX_RECENT])

    # ---------------------------------------------------------------- project file
    def save(self, items: list[WellEntry | WellRef], path: Path) -> None:
        """Writes the project (raises OSError) and makes it the current, saved one.
        `items`: the project's wells (ProjectWells.items)."""
        save_project(path, items)
        self.project_path = path
        self.dirty = False
        self.recovery.discard()  # everything is in the project now
        self.add_recent(path)

    def opened(self, path: str | Path) -> None:
        """A project file was opened: it is the current project, with no changes yet."""
        self.project_path = Path(path)
        self.dirty = False
        self.add_recent(path)

    # ---------------------------------------------------------------- autosave and recovery
    def autosave(self, items: list[WellEntry | WellRef]) -> bool:
        """Saves the project's wells for recovery if there are unsaved changes. True if it saved."""
        if not (self.dirty and items):
            return False
        try:
            self.recovery.save(items, self.project_path)
        except OSError:
            log.exception("Autosave failed")
            return False
        return True

    def restored(self) -> None:
        """The autosave was opened: it stays attached to the project it came from, still unsaved."""
        _saved, self.project_path = self.recovery.info()
        self.dirty = True

    def closed_normally(self) -> None:
        self.recovery.discard()
