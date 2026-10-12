"""Autosave, crash recovery and the error log."""

import logging
import sys

import pytest
from PySide6.QtCore import QSettings

from innopetrol.errors import ErrorReporter, setup_logging
from innopetrol.ui.main_window import MainWindow


def make_window(qtbot, tmp_path):
    w = MainWindow(QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))
    qtbot.addWidget(w)
    return w


def finish(w):
    w.dirty = False


def test_autosave_and_restore_after_a_crash(qtbot, tmp_path, samples):
    w = make_window(qtbot, tmp_path)
    assert w.data_dir == tmp_path  # tests never touch the user's real data folder
    assert not w.autosave()  # nothing open
    w.open_las([str(samples / "Testdata.las")])
    n_tracks = len(w.docs[0].layout.tracks)
    w.docs[0].remove_track(2)
    assert w.autosave() and w.recovery.pending()
    finish(w)  # the "crash": the window goes away without a normal close

    again = make_window(qtbot, tmp_path)
    again.check_recovery()  # the question is answered Yes by the test fixture
    assert len(again.docs) == 1 and len(again.docs[0].layout.tracks) == n_tracks - 1
    assert again.dirty and again.project_path is None  # restored, still to be saved
    finish(again)  # changes discarded by the user
    again.close()
    assert not again.recovery.pending()  # a normal exit deletes the autosave


def test_saving_the_project_discards_the_autosave(qtbot, tmp_path, samples):
    w = make_window(qtbot, tmp_path)
    w.open_las([str(samples / "Testdata.las")])
    w.autosave()
    w.project_path = tmp_path / "p.ipproj"
    assert w.save_project()
    assert not w.recovery.pending()
    finish(w)


def test_recovered_project_keeps_its_path(qtbot, tmp_path, samples):
    w = make_window(qtbot, tmp_path)
    w.open_las([str(samples / "Testdata.las")])
    w.project_path = tmp_path / "mine.ipproj"
    w.autosave()
    finish(w)
    again = make_window(qtbot, tmp_path)
    again.check_recovery()
    assert again.project_path == tmp_path / "mine.ipproj" and again.dirty
    finish(again)


def test_error_reporter_logs_autosaves_and_reports(tmp_path):
    log_path = setup_logging(tmp_path)
    shown, saves = [], []
    reporter = ErrorReporter(
        log_path, before_report=lambda: saves.append(1) or True, show=lambda *args: shown.append(args)
    )
    try:
        raise ValueError("boom")
    except ValueError:
        reporter(*sys.exc_info())
    for h in logging.getLogger("innopetrol").handlers:
        h.flush()
    text = log_path.read_text(encoding="utf-8")
    assert "ValueError: boom" in text and "Traceback" in text
    assert saves == [1] and shown[0][0] == "ValueError: boom" and shown[0][3] is True


def test_error_while_reporting_is_only_logged(tmp_path):
    log_path = tmp_path / "x.log"
    calls = []

    def show(*args):
        calls.append(args)
        reporter(RuntimeError, RuntimeError("again"), None)  # nested error: must not recurse

    reporter = ErrorReporter(log_path, show=show)
    reporter(ValueError, ValueError("first"), None)
    assert len(calls) == 1


@pytest.fixture(autouse=True)
def _restore_excepthook():
    hook = sys.excepthook
    yield
    sys.excepthook = hook
