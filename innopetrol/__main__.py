"""Punto de entrada: `python -m innopetrol [archivos.las | proyecto.ipproj]` o `innopetrol`."""

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
    window.show()
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    projects = [a for a in args if a.endswith(SUFFIX)]
    if projects:
        window.open_project(projects[0])
    las = [a for a in args if a.lower().endswith(".las")]
    if las:
        window.open_las(las)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
