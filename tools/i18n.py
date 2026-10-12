"""Translation catalog maintenance.

    uv run python tools/i18n.py update    # extract strings from the code and update every .po
    uv run python tools/i18n.py compile   # compile .po -> .mo (run after translating)
    uv run python tools/i18n.py init fr   # start a new language

Edit the .po files with any text editor or with Poedit (https://poedit.net).
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCALE = ROOT / "innopetrol" / "locale"
POT = LOCALE / "innopetrol.pot"


def run(*args: str) -> None:
    subprocess.run([sys.executable, "-m", "babel.messages.frontend", *args], check=True, cwd=ROOT)


def extract() -> None:
    run(
        "extract",
        "--project=InnoPetrol",
        "--no-location",
        "--sort-output",
        "--width=100",
        "-k",
        "_",
        "-k",
        "N_",
        "-k",
        "ngettext:1,2",
        "-o",
        str(POT),
        "innopetrol",
    )


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "update"
    if cmd == "update":
        extract()
        run(
            "update",
            "-i",
            str(POT),
            "-d",
            str(LOCALE),
            "-D",
            "innopetrol",
            "--no-fuzzy-matching",
            "--width=100",
            "--ignore-obsolete",
        )
    elif cmd == "compile":
        run("compile", "-d", str(LOCALE), "-D", "innopetrol", "--statistics")
    elif cmd == "init":
        extract()
        run("init", "-i", str(POT), "-d", str(LOCALE), "-D", "innopetrol", "-l", sys.argv[2])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
