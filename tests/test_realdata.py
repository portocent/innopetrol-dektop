"""The program over real well files (Kansas Geological Survey archive, ~1500 LAS files).

Not part of the normal run: the files are downloaded once to ~/.cache/innopetrol (44 MB).
    uv run pytest -m realdata
Set INNOPETROL_REALDATA to a folder to use your own files instead.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

pytestmark = [pytest.mark.realdata, pytest.mark.timeout(1800)]


def test_every_real_file_loads_draws_and_computes(tmp_path, qapp):
    import realdata

    folder = Path(os.environ["INNOPETROL_REALDATA"]) if os.environ.get("INNOPETROL_REALDATA") else realdata.kgs_corpus()
    files = realdata.well_files(folder)
    assert files, f"no well files in {folder}"
    results = realdata.run(files, tmp_path / "report.csv")
    print("\n" + realdata.summary(results))
    failed = [f"{Path(r.path).name} ({r.stage}): {r.error}" for r in results if not r.ok]
    assert not failed, "\n".join(failed[:30])
    assert max(r.seconds for r in results) < 20  # no file should take minutes
