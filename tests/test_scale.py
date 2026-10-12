"""A project with hundreds of real wells (Kansas Geological Survey archive): it must open at once.

Not part of the normal run (see test_realdata.py):
    uv run pytest -m realdata
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

pytestmark = [pytest.mark.realdata, pytest.mark.timeout(1800)]


def test_project_with_500_wells_opens_without_loading_them(tmp_path, qapp):
    import realdata

    folder = Path(os.environ["INNOPETROL_REALDATA"]) if os.environ.get("INNOPETROL_REALDATA") else realdata.kgs_corpus()
    files = realdata.well_files(folder)[:500]
    times = realdata.scale_benchmark(files, tmp_path)
    print("\n" + "\n".join(f"{k:10} {v:8.3f} s" for k, v in times.items()))
    assert times["open"] < 2
    assert times["filter"] < 0.2
    assert times["open"] < times["load_all"] / 10  # the point of not loading the data
