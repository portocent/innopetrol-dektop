"""Paths to the program's images, independent of the operating system.

The original code used "statics\\\\images\\\\..." (Windows only) and inconsistent capitalization
(d1.png vs d1.PNG), which is why icons were missing on macOS/Linux.
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
