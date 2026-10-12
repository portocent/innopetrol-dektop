"""The project catalog: well summaries without reading the data, and projects whose wells are not loaded."""

import json
import math
import shutil

from innopetrol.model.catalog import WellRef, WellSummary, summaries_from_file
from innopetrol.model.mnemonics import build_triple_combo
from innopetrol.model.project import WellEntry, is_open, load_ref, read_project, save_project
from innopetrol.model.tops import Top


def test_header_summary_matches_a_full_load(samples, testdata_well):
    [(source, header)] = summaries_from_file(samples / "Testdata.las")
    full = WellSummary.from_well(testdata_well)
    assert source is None
    assert header.name == full.name and header.depth_unit == full.depth_unit
    assert header.curves == full.curves
    assert math.isclose(header.start, full.start) and math.isclose(header.stop, full.stop)


def test_summary_dict_roundtrip(testdata_well):
    s = WellSummary.from_well(testdata_well)
    assert WellSummary.from_dict(json.loads(json.dumps(s.to_dict()))) == s


def test_project_keeps_wells_that_are_not_loaded(tmp_path, samples, testdata_well):
    for name in ("Testdata.las", "TotalDepthPrueba.las"):
        shutil.copy(samples / name, tmp_path / name)
    well = testdata_well
    well.path = tmp_path / "Testdata.las"
    well.tops = [Top("A", 7700, "#ff0000")]
    other_path = tmp_path / "TotalDepthPrueba.las"
    other = WellRef(other_path, None, summaries_from_file(other_path)[0][1])
    other.entry = {"name": "1-5", "tops": [{"name": "B", "depth": 100.0, "color": "#00ff00"}], "custom": 42}
    save_project(tmp_path / "p.ipproj", [WellEntry(well, build_triple_combo(well), open=True), other])

    refs = read_project(tmp_path / "p.ipproj")
    assert [r.name for r in refs] == ["Test Well 1", "1-5"]
    assert [is_open(r) for r in refs] == [True, False]
    assert refs[1].entry is not None and refs[1].entry["custom"] == 42  # written back unchanged
    errors: list[str] = []
    entry = load_ref(refs[0], errors)
    assert not errors and entry is not None and entry.well.tops[0].name == "A" and entry.open

    # Saved again from a different folder: the paths still point to the same files
    (tmp_path / "sub").mkdir()
    save_project(tmp_path / "sub" / "q.ipproj", refs)
    again = read_project(tmp_path / "sub" / "q.ipproj")
    assert [r.path for r in again] == [r.path for r in refs] and not any(r.missing for r in again)


def test_version_1_project_opens_every_well(tmp_path, samples):
    shutil.copy(samples / "Testdata.las", tmp_path / "Testdata.las")
    data = {"format": "innopetrol-project", "version": 1, "wells": [{"path": "Testdata.las", "name": "Test Well 1"}]}
    (tmp_path / "old.ipproj").write_text(json.dumps(data), encoding="utf-8")
    [ref] = read_project(tmp_path / "old.ipproj")
    assert is_open(ref) and ref.summary.curves  # the summary comes from the file header


def test_missing_file_is_marked(tmp_path):
    data = {"format": "innopetrol-project", "version": 2, "wells": [{"path": "gone.las", "name": "Gone"}]}
    (tmp_path / "p.ipproj").write_text(json.dumps(data), encoding="utf-8")
    [ref] = read_project(tmp_path / "p.ipproj")
    assert ref.missing and ref.name == "Gone"
    errors: list[str] = []
    assert load_ref(ref, errors) is None and errors
