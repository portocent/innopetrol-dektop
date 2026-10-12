"""Rutas a imágenes del programa, independientes del sistema operativo.

El código original usaba "statics\\\\images\\\\..." (sólo Windows) y nombres con mayúsculas
inconsistentes (d1.png vs d1.PNG), por eso los iconos no aparecían en macOS/Linux.
"""

from pathlib import Path

IMAGES = Path(__file__).resolve().parent / "statics" / "images"


def image(name: str) -> str:
    return str(IMAGES / name)


def icon(name: str):
    from PySide6.QtGui import QIcon

    return QIcon(image(name))


def app_icon():
    return icon("logo-08.png")
