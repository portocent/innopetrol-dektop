"""Entry point: `python -m innopetrol [files.las | project.ipproj]` or `innopetrol`."""

import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from innopetrol.model.project import SUFFIX
    from innopetrol.resources import app_icon
    from innopetrol.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("InnoPetrol")
    app.setOrganizationName("InnoPetrol")
    app.setWindowIcon(app_icon())
    app.setStyle("Fusion")
    window = MainWindow()
    from innopetrol.errors import ErrorReporter, setup_logging

    log_path = setup_logging(window.data_dir)
    ErrorReporter(log_path, before_report=window.autosave).install()
    window.show()
    if "--smoke-test" not in sys.argv:
        window.check_recovery()
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    projects = [a for a in args if a.lower().endswith(SUFFIX)]
    if projects:
        window.open_project(projects[0])
    from innopetrol.model.io import is_well_file

    las = [a for a in args if is_well_file(a)]
    if las:
        window.open_las(las)
    if "--smoke-test" in sys.argv:
        return _smoke_test(app, window, expected=len(las))
    return app.exec()


def _smoke_test(app, window, expected: int) -> int:
    """Packaged executable check: opens the LAS files, draws and exits (exit code 0 = OK).

    Used by continuous integration on Windows, Linux and macOS to verify that the bundle contains
    Qt, the icons and everything else it needs, with nobody at the keyboard.
    """
    from PySide6.QtCore import QTimer

    from innopetrol import i18n
    from innopetrol.resources import IMAGES

    result = {"code": 1}

    def check():
        ok = len(window.docs) == expected and (IMAGES / "d1.png").exists()
        # The translation catalogs must be bundled too: switching to Spanish must translate.
        # set_language() persists the choice, so the user's previous setting is restored afterwards.
        previous_language = window.settings.value("language")
        current = i18n.current_language()
        window.set_language("es")
        ok = ok and window.a_fit.text() == "Ajustar a la ventana"
        window.set_language(current)
        if previous_language is None:
            window.settings.remove("language")
        else:
            window.settings.setValue("language", previous_language)
        for view in window.views.values():
            ok = ok and not view.canvas.grab().isNull()
            view.confirm_close = False
        window.dirty = False
        result["code"] = 0 if ok else 1
        print("smoke-test", "OK" if ok else "FAILED", f"({len(window.docs)}/{expected} wells)", flush=True)
        app.quit()

    QTimer.singleShot(1500, check)
    app.exec()
    return result["code"]


if __name__ == "__main__":
    sys.exit(main())
