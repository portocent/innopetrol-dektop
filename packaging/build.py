"""Builds the InnoPetrol executable for the current operating system.

    uv run --group build python packaging/build.py

Output in dist/InnoPetrol/ (Windows and Linux) or dist/InnoPetrol.app (macOS), plus what users
download on each system:
  Windows  .zip and an installer (InnoPetrol-<version>-windows-setup.exe) if Inno Setup is installed
  macOS    .zip and a disk image (.dmg)
  Linux    .tar.gz with install.sh (adds the program to the applications menu)
It must run on each system: PyInstaller does not cross-compile.
"""

import os
import platform
import shutil
import subprocess
import sys
import tarfile
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
        # The LGPL requires shipping the licence texts with every copy.
        "--add-data", f"{ROOT / 'COPYING'}:.",
        "--add-data", f"{ROOT / 'COPYING.LESSER'}:.",
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
    archive = ROOT / "dist" / f"{NAME}-{version()}-{system}-{platform.machine().lower()}"
    outputs = []
    if system == "linux":
        # tar keeps the executable permissions and is what Linux users expect.
        shutil.copy2(ROOT / "packaging" / "install-linux.sh", target / "install.sh")
        with tarfile.open(f"{archive}.tar.gz", "w:gz") as tar:
            tar.add(target, arcname=NAME)
        outputs.append(f"{archive}.tar.gz")
    else:
        shutil.make_archive(str(archive), "zip", target.parent, target.name)
        outputs.append(f"{archive}.zip")
    if system == "macos":
        outputs.append(make_dmg(target, archive))
    if system == "windows":
        setup = make_windows_installer()
        if setup:
            outputs.append(setup)
    print(f"\nDone: {target}\n" + "\n".join(f"  {o}" for o in outputs))


def version() -> str:
    sys.path.insert(0, str(ROOT))
    from innopetrol import __version__

    return __version__


def make_dmg(app: Path, archive: Path) -> str:
    """Disk image with the app and a shortcut to Applications (drag to install)."""
    staging = ROOT / "build" / "dmg"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    shutil.copytree(app, staging / app.name, symlinks=True)
    os.symlink("/Applications", staging / "Applications")
    dmg = f"{archive}.dmg"
    subprocess.run(["hdiutil", "create", "-volname", NAME, "-srcfolder", str(staging), "-ov", "-format", "UDZO",
                    dmg], check=True)
    return dmg


def make_windows_installer() -> str | None:
    """Installer built with Inno Setup (skipped with a message if it is not installed)."""
    iscc = shutil.which("iscc") or next((str(p) for p in (
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Inno Setup 6" / "ISCC.exe") if p.exists()), None)
    if iscc is None:
        print("Inno Setup not found: the installer was not built (the .zip is still available).")
        return None
    subprocess.run([iscc, f"/DAppVersion={version()}", str(ROOT / "packaging" / "innopetrol.iss")], check=True)
    return str(ROOT / "dist" / f"{NAME}-{version()}-windows-setup.exe")


if __name__ == "__main__":
    main()
