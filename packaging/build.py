"""Builds the InnoPetrol executable for the current operating system.

    uv run --group build python packaging/build.py

Output in dist/InnoPetrol/ (Windows and Linux) or dist/InnoPetrol.app (macOS), plus a .zip ready
to distribute. It must run on each system: PyInstaller does not cross-compile.
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
        "--windowed",  # no console
        "--noconfirm",
        "--clean",
        "--icon", str(ROOT / "innopetrol" / "statics" / "images" / "logo-08.png"),
        "--add-data", f"{ROOT / 'innopetrol' / 'statics'}:innopetrol/statics",
        "--add-data", f"{ROOT / 'innopetrol' / 'locale'}:innopetrol/locale",  # interface translations
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
        # modules PyInstaller pulls in through optional dependencies that the app does not use
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
    print(f"\nDone: {target}\nZip:  {archive}.zip")


if __name__ == "__main__":
    main()
