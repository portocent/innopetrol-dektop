"""The wells of the project: every WellRef, and the WellDocument of the ones that are loaded.

A well can be in three states: only in the project (a WellRef with its summary), loaded (it has a
WellDocument, its data is in memory) and shown (it also has a window). This class keeps the first
two; the main window keeps the windows. Loading many wells shows a progress dialog that can be
cancelled.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QApplication, QProgressDialog, QWidget

from innopetrol.i18n import _
from innopetrol.model.catalog import WellRef, WellSummary
from innopetrol.model.project import WellEntry, load_ref, well_dict
from innopetrol.ui.document import WellDocument

# Below this many wells, loading shows only a wait cursor (a progress dialog would just flash).
PROGRESS_FROM = 4


def entry_of(doc: WellDocument, is_open: bool = False) -> WellEntry:
    """What a project stores about a loaded well."""
    return WellEntry(
        doc.well, doc.layout, doc.petro, doc.depth_reference, doc.display_unit, dict(doc.curve_units), is_open
    )


class ProjectWells(QObject):
    added = Signal(object)  # WellRef
    removed = Signal(object)  # WellRef
    loaded = Signal(object)  # WellRef (its document is in docs)
    unloaded = Signal(object)  # WellRef

    def __init__(self, make_doc: Callable[[WellEntry], WellDocument], parent=None):
        """`make_doc` turns a loaded project entry into a document (the main window wires it up)."""
        super().__init__(parent)
        self.make_doc = make_doc
        self.refs: list[WellRef] = []
        self.docs: dict[WellRef, WellDocument] = {}

    def __len__(self) -> int:
        return len(self.refs)

    def loaded_docs(self) -> list[WellDocument]:
        """Loaded wells, in project order."""
        return [self.docs[r] for r in self.refs if r in self.docs]

    def ref_of(self, doc: WellDocument) -> WellRef | None:
        return next((r for r, d in self.docs.items() if d is doc), None)

    def find(self, ref: WellRef) -> WellRef | None:
        """The well of the project that points to the same file (and frame) as `ref`."""
        return next((r for r in self.refs if r.same_file(ref)), None)

    # ---------------------------------------------------------------- adding and removing
    def add(self, ref: WellRef, doc: WellDocument | None = None) -> None:
        self.refs.append(ref)
        if doc is not None:
            ref.entry = None
            self.docs[ref] = doc
        self.added.emit(ref)

    def remove(self, ref: WellRef) -> None:
        self.docs.pop(ref, None)
        self.refs.remove(ref)
        self.removed.emit(ref)

    def clear(self) -> None:
        for ref in list(self.refs):
            self.remove(ref)

    def unload(self, ref: WellRef) -> None:
        """Free a well's data. What the project stores about it is kept, so nothing is lost."""
        doc = self.docs.pop(ref, None)
        if doc is None:
            return
        ref.entry = well_dict(entry_of(doc))
        ref.summary = WellSummary.from_well(doc.well)
        self.unloaded.emit(ref)

    # ---------------------------------------------------------------- loading
    def ensure_loaded(self, refs: Iterable[WellRef], parent: QWidget | None = None) -> list[str]:
        """Load the wells that are not loaded yet. Returns the problems found (one line each)."""
        pending = [r for r in refs if r not in self.docs]
        errors: list[str] = []
        if not pending:
            return errors
        progress = None
        if len(pending) >= PROGRESS_FROM:
            progress = QProgressDialog(_("Loading wells…"), _("Cancel"), 0, len(pending), parent)
            progress.setWindowTitle(_("Loading wells"))
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(300)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            for i, ref in enumerate(pending):
                if progress is not None:
                    progress.setValue(i)
                    progress.setLabelText(_("Loading {well}…").format(well=ref.name))
                    if progress.wasCanceled():
                        break
                self._load(ref, errors)
        finally:
            QApplication.restoreOverrideCursor()
            if progress is not None:
                progress.close()
        return errors

    def _load(self, ref: WellRef, errors: list[str]) -> None:
        if ref.path is not None and not ref.path.exists():
            ref.missing = True
            errors.append(_("{well}: file not found: {path}").format(well=ref.name, path=ref.path))
            return
        entry = load_ref(ref, errors)
        if entry is None:
            return
        self.docs[ref] = self.make_doc(entry)
        ref.entry = None  # the document holds the state now
        self.loaded.emit(ref)

    # ---------------------------------------------------------------- saving
    def items(self, shown: Callable[[WellDocument], bool]) -> list[WellEntry | WellRef]:
        """What the project file stores: loaded wells as entries, the others as they were read.
        `shown` tells whether a document has its window open."""
        return [entry_of(self.docs[r], shown(self.docs[r])) if r in self.docs else r for r in self.refs]
