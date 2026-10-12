"""Session state without widgets: recent files, saving, autosave and recovery."""

from PySide6.QtCore import QSettings

from innopetrol.model.mnemonics import build_triple_combo
from innopetrol.ui.document import WellDocument
from innopetrol.ui.session import MAX_RECENT, Session


def make(tmp_path) -> Session:
    return Session(QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))


def test_recent_files_most_recent_first_without_duplicates(tmp_path):
    s = make(tmp_path)
    for i in range(MAX_RECENT + 2):
        s.add_recent(f"/p/{i}.las")
    s.add_recent("/p/3.las")
    recent = s.recent()
    assert recent[0] == "/p/3.las" and len(recent) == MAX_RECENT and recent.count("/p/3.las") == 1


def test_save_autosave_and_restore(tmp_path, testdata_well, qapp):
    s = make(tmp_path)
    docs = [WellDocument(testdata_well, build_triple_combo(testdata_well))]
    assert not s.autosave(docs)  # nothing changed
    s.dirty = True
    assert s.autosave(docs) and s.recovery.pending()
    s.save(docs, tmp_path / "p.ipproj")
    assert not s.dirty and not s.recovery.pending() and s.recent()[0].endswith("p.ipproj")
    s.dirty = True
    s.autosave(docs)
    again = make(tmp_path)  # next start
    again.restored()
    assert again.dirty and again.project_path == tmp_path / "p.ipproj"
    again.closed_normally()
    assert not again.recovery.pending()
