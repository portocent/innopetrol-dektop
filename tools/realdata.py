"""Runs InnoPetrol over a corpus of real well files and reports what happens with each one.

    uv run python tools/realdata.py                     # Kansas Geological Survey LAS archive (downloaded once)
    uv run python tools/realdata.py --folder PATH       # your own files (Volve, company data…)
    uv run python tools/realdata.py --limit 200         # only the first N files
    uv run python tools/realdata.py --scale 500         # time a project with N wells (no per-file checks)

For each file: load it, build the automatic layout, draw part of it and, when the well has gamma ray and
density, compute the petrophysics. The report (CSV, one row per file) lists failures, corrections made
on load, unrecognized units and curves without a family, so real-world problems can be fixed.

Third-party data is never stored in the repository: it is downloaded to a local cache
(~/.cache/innopetrol) or read from a folder you choose.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
import traceback
import urllib.request
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

KGS_URL = "https://www.kgs.ku.edu/PRS/Scans/Log_Summary/2001_2005.zip"
CACHE = Path(os.environ.get("INNOPETROL_DATA", Path.home() / ".cache" / "innopetrol"))
WELL_SUFFIXES = (".las", ".dlis", ".dls")


@dataclass
class FileResult:
    path: str
    ok: bool = True
    stage: str = ""  # where it failed: load, layout, draw, petro
    error: str = ""
    wells: int = 0
    samples: int = 0
    curves: int = 0
    notes: list[str] = field(default_factory=list)
    unknown_units: list[str] = field(default_factory=list)
    unknown_curves: list[str] = field(default_factory=list)
    petro: bool = False
    seconds: float = 0.0


def kgs_corpus(url: str = KGS_URL) -> Path:
    """Downloads and unpacks the KGS archive once; returns the folder with the files."""
    target = CACHE / "kgs" / Path(url).stem
    if target.exists() and any(target.rglob("*")):
        return target
    target.mkdir(parents=True, exist_ok=True)
    archive = target.parent / Path(url).name
    if not archive.exists():
        print(f"Downloading {url} …", flush=True)
        request = urllib.request.Request(url, headers={"User-Agent": "InnoPetrol test corpus"})
        with urllib.request.urlopen(request, timeout=120) as r, open(archive, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
    _extract(archive, target)
    return target


def _extract(archive: Path, target: Path) -> None:
    """Unpacks well files only, flattening paths (nested archives are opened too)."""
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            name = Path(info.filename).name
            if info.is_dir() or not name:
                continue
            if name.lower().endswith(".zip"):
                inner = target / name
                inner.write_bytes(z.read(info))
                _extract(inner, target)
                inner.unlink()
            elif name.lower().endswith(WELL_SUFFIXES):
                (target / name).write_bytes(z.read(info))


def check_file(path: Path) -> FileResult:
    from innopetrol.model import petro, units
    from innopetrol.model.io import load_wells
    from innopetrol.model.mnemonics import build_triple_combo, family_of, find_curve
    from innopetrol.render.export import export_png

    result = FileResult(str(path))
    start = time.perf_counter()
    stage = "load"
    try:
        wells = load_wells(path)
        result.wells = len(wells)
        for w in wells:
            result.samples += w.depth.size
            result.curves += len(w.curves)
            result.notes += w.notes
            result.unknown_units += sorted(
                {c.unit for c in w.curves.values() if c.unit and not units.normalize(c.unit)}
            )
            result.unknown_curves += [m for m in w.curves if family_of(m) is None]
            stage = "layout"
            layout = build_triple_combo(w)
            stage = "draw"
            top = w.start
            bottom = min(w.stop, top + (200 if w.depth_unit == "m" else 600))
            export_png(_null_png(), w, layout, 500, top, bottom, dpi=40, heading=True)
            stage = "petro"
            gr, rhob = find_curve(w, "gamma_ray"), find_curve(w, "density")
            if gr and rhob:
                params = petro.PetroParams(
                    gr_curve=gr,
                    rhob_curve=rhob,
                    nphi_curve=find_curve(w, "neutron"),
                    rt_curve=find_curve(w, "deep_res"),
                    bad_hole=True,
                    cali_curve=find_curve(w, "caliper"),
                    bs_curve=find_curve(w, "bit_size"),
                    drho_curve=find_curve(w, "density_corr"),
                )
                petro.compute(w, params)
                result.petro = True
    except Exception as e:
        result.ok, result.stage = False, stage
        result.error = f"{type(e).__name__}: {e}".splitlines()[0][:300]
        if os.environ.get("REALDATA_TRACEBACK"):
            traceback.print_exc()
    result.seconds = time.perf_counter() - start
    return result


def _null_png() -> Path:
    return CACHE / "render-check.png"


def well_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*") if p.suffix.lower() in WELL_SUFFIXES)


def run(files: list[Path], report: Path) -> list[FileResult]:
    from PySide6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    CACHE.mkdir(parents=True, exist_ok=True)
    results = []
    for i, f in enumerate(files, 1):
        results.append(check_file(f))
        if i % 100 == 0:
            print(f"  {i}/{len(files)}", flush=True)
    with open(report, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            ["file", "ok", "stage", "error", "wells", "samples", "curves", "petro", "seconds", "notes", "unknown_units"]
        )
        for r in results:
            w.writerow(
                [
                    Path(r.path).name,
                    r.ok,
                    r.stage,
                    r.error,
                    r.wells,
                    r.samples,
                    r.curves,
                    r.petro,
                    f"{r.seconds:.3f}",
                    " | ".join(r.notes),
                    " ".join(r.unknown_units),
                ]
            )
    return results


def summary(results: list[FileResult]) -> str:
    failed = [r for r in results if not r.ok]
    lines = [
        f"Files: {len(results)} · OK: {len(results) - len(failed)} · failed: {len(failed)}",
        f"Petrophysics computed: {sum(r.petro for r in results)}",
        f"Files corrected on load: {sum(bool(r.notes) for r in results)}",
        f"Slowest: {max((r.seconds for r in results), default=0):.2f} s",
    ]
    by_error = Counter(f"{r.stage}: {r.error.split(':')[0]}" for r in failed)
    if by_error:
        lines.append("Failures by kind:")
        lines += [f"  {n:5d}  {kind}" for kind, n in by_error.most_common(15)]
    units_c = Counter(u.upper() for r in results for u in set(r.unknown_units))
    if units_c:
        lines.append("Most common unrecognized units:")
        lines += [f"  {n:5d}  {u}" for u, n in units_c.most_common(25)]
    curves_c = Counter(m.upper() for r in results for m in set(r.unknown_curves))
    lines.append("Most common curves without a family:")
    lines += [f"  {n:5d}  {m}" for m, n in curves_c.most_common(40)]
    return "\n".join(lines)


def scale_benchmark(files: list[Path], folder: Path) -> dict[str, float]:
    """Seconds taken by a project with these wells: reading the headers, saving the project, opening
    it in the main window (nothing loaded), filtering the tree, and loading every well (as before
    projects kept wells unloaded)."""
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from innopetrol.model.catalog import refs_from_file
    from innopetrol.model.project import load_project, save_project
    from innopetrol.ui.main_window import MainWindow

    _app = QApplication.instance() or QApplication([])
    times: dict[str, float] = {}
    t = time.perf_counter()
    refs = [ref for f in files for ref in refs_from_file(f)]
    times["headers"] = time.perf_counter() - t
    project = folder / "scale.ipproj"
    t = time.perf_counter()
    save_project(project, refs)
    times["save"] = time.perf_counter() - t
    window = MainWindow(QSettings(str(folder / "scale.ini"), QSettings.Format.IniFormat))
    t = time.perf_counter()
    window.open_project(project)
    times["open"] = time.perf_counter() - t
    t = time.perf_counter()
    window.tree.set_filter("", "density")
    window.tree.set_filter("", "")
    times["filter"] = (time.perf_counter() - t) / 2
    window.dirty = False
    window.close()
    t = time.perf_counter()
    load_project(project)
    times["load_all"] = time.perf_counter() - t
    return times


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--folder", type=Path, help="folder with your own LAS/DLIS files")
    parser.add_argument("--limit", type=int, default=0, help="only the first N files")
    parser.add_argument("--report", type=Path, default=Path("realdata-report.csv"))
    parser.add_argument("--scale", type=int, default=0, help="time a project with the first N files")
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    folder = args.folder or kgs_corpus()
    files = well_files(folder)
    if args.limit:
        files = files[: args.limit]
    if args.scale:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            times = scale_benchmark(files[: args.scale], Path(tmp))
        for name, seconds in times.items():
            print(f"{name:10} {seconds:8.3f} s")
        return 0
    print(f"Checking {len(files)} files from {folder}", flush=True)
    results = run(files, args.report)
    print(summary(results))
    print(f"Report: {args.report.resolve()}")
    return 1 if any(not r.ok for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
