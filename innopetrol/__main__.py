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
    projects = [a for a in args if a.lower().endswith(SUFFIX)]
    if projects:
        window.open_project(projects[0])
    las = [a for a in args if a.lower().endswith(".las")]
    if las:
        window.open_las(las)
    if "--smoke-test" in sys.argv:
        return _smoke_test(app, window, expected=len(las))
    return app.exec()


def _smoke_test(app, window, expected: int) -> int:
    """Verificación del ejecutable empaquetado: abre los LAS, dibuja y sale (código 0 = bien).

    La usa la integración continua en Windows, Linux y macOS: comprueba que el paquete incluye
    Qt, los iconos y todo lo necesario, sin intervención de nadie.
    """
    from PySide6.QtCore import QTimer

    from innopetrol.resources import IMAGES

    result = {"code": 1}

    def check():
        ok = len(window.docs) == expected and (IMAGES / "d1.png").exists()
        for view in window.views.values():
            ok = ok and not view.canvas.grab().isNull()
            view.confirm_close = False
        window.dirty = False
        result["code"] = 0 if ok else 1
        print("smoke-test", "OK" if ok else "FALLÓ", f"({len(window.docs)}/{expected} pozos)", flush=True)
        app.quit()

    QTimer.singleShot(1500, check)
    app.exec()
    return result["code"]


if __name__ == "__main__":
    sys.exit(main())
