"""Genera el ejecutable de InnoPetrol para el sistema operativo actual.

    uv run --group build python packaging/build.py

Resultado en dist/InnoPetrol/ (Windows y Linux) o dist/InnoPetrol.app (macOS), más un .zip
listo para distribuir. Hay que ejecutarlo en cada sistema: PyInstaller no compila de forma cruzada.
"""

import platform
import shutil
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent.parent
NAME = "InnoPetrol"


def main() -> None:
    args = [
        str(ROOT / "packaging" / "innopetrol_app.py"),
        "--name", NAME,
        "--windowed",  # sin consola
        "--noconfirm",
        "--clean",
        "--icon", str(ROOT / "innopetrol" / "statics" / "images" / "logo-08.png"),
        "--add-data", f"{ROOT / 'innopetrol' / 'statics'}:innopetrol/statics",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
        # módulos que PyInstaller arrastra por dependencias opcionales y la app no usa
        "--exclude-module", "tkinter",
        "--exclude-module", "pandas",
        "--exclude-module", "matplotlib",
        "--exclude-module", "PySide6.QtNetwork",
        "--exclude-module", "PySide6.QtQml",
        "--exclude-module", "PySide6.QtQuick",
    ]
    if sys.platform == "darwin":
        args += ["--osx-bundle-identifier", "com.innopetrol.visor"]
    PyInstaller.__main__.run(args)

    system = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    target = ROOT / "dist" / (f"{NAME}.app" if sys.platform == "darwin" else NAME)
    archive = ROOT / "dist" / f"{NAME}-{system}-{platform.machine().lower()}"
    shutil.make_archive(str(archive), "zip", target.parent, target.name)
    print(f"\nListo: {target}\nZip:   {archive}.zip")


if __name__ == "__main__":
    main()
