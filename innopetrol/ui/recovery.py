"""Autosave and crash recovery.

While there are unsaved changes, the open wells are saved every few minutes as a project in the
application's data folder. A normal exit deletes it; if the file is still there at the next start,
the program did not close properly and offers to restore the work.
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

from innopetrol.model.project import WellEntry, save_project

AUTOSAVE_NAME = "autosave.ipproj"
INFO_NAME = "autosave.json"


class Recovery:
    def __init__(self, folder: Path):
        self.folder = Path(folder)

    @property
    def path(self) -> Path:
        return self.folder / AUTOSAVE_NAME

    @property
    def _info_path(self) -> Path:
        return self.folder / INFO_NAME

    def save(self, entries: list[WellEntry], project_path: Path | None) -> None:
        """Writes the autosave atomically: a crash while writing never leaves a half-written file."""
        self.folder.mkdir(parents=True, exist_ok=True)
        tmp = self.folder / (AUTOSAVE_NAME + ".tmp")
        save_project(tmp, entries)
        os.replace(tmp, self.path)
        info = {"saved": datetime.datetime.now().isoformat(timespec="seconds"),
                "project": str(project_path) if project_path else None}
        self._info_path.write_text(json.dumps(info), encoding="utf-8")

    def pending(self) -> bool:
        return self.path.exists()

    def info(self) -> tuple[str, Path | None]:
        """(when it was saved, the project it belonged to or None)."""
        try:
            data = json.loads(self._info_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        saved = data.get("saved") or datetime.datetime.fromtimestamp(self.path.stat().st_mtime).isoformat(
            timespec="seconds")
        project = data.get("project")
        return saved.replace("T", " "), Path(project) if project else None

    def discard(self) -> None:
        for p in (self.path, self._info_path, self.folder / (AUTOSAVE_NAME + ".tmp")):
            try:
                p.unlink()
            except FileNotFoundError:
                pass
