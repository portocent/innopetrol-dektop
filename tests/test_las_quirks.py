"""Problems found in real-world LAS files. Each case is generated so no third-party data is needed."""

import numpy as np
import pytest

from innopetrol.model.well import Well

CURVES = [" DEPT.M : depth", " GR.GAPI : gamma", " RHOB.G/C3 : density"]


def well_header(unit="M", null="-999.25", step="0.5", name=" WELL.  Q-1 : WELL"):
    lines = [
        f" STRT.{unit} 1000.0 : START",
        f" STOP.{unit} 1002.0 : STOP",
        f" STEP.{unit} {step} : STEP",
        f" NULL. {null} : NULL",
    ]
    return lines + ([name] if name else [])


def write_las(path, rows, well=None, curves=CURVES, version="2.0"):
    text = [
        "~VERSION INFORMATION",
        f" VERS.   {version} : CWLS LOG ASCII STANDARD",
        " WRAP.   NO : one line",
        "~WELL INFORMATION",
        *(well or well_header()),
        "~CURVE INFORMATION",
        *curves,
        "~A  DEPTH  GR  RHOB",
        *rows,
    ]
    path.write_text("\n".join(text) + "\n", encoding="utf-8")
    return Well.from_las(path)


def is_clean(w: Well) -> bool:
    return bool(np.all(np.diff(w.depth) > 0) and np.isfinite(w.depth).all())


def test_duplicate_depths_keep_first(tmp_path):
    w = write_las(tmp_path / "a.las", ["1000.0 50 2.4", "1000.5 60 2.3", "1000.5 61 2.31", "1001.0 70 2.2"])
    assert is_clean(w) and w.curves["GR"].values.tolist() == [50, 60, 70]
    assert any("repeated depth" in n for n in w.notes)


def test_partially_decreasing_depth_is_sorted(tmp_path):
    w = write_las(tmp_path / "a.las", ["1000.0 50 2.4", "1001.0 70 2.2", "1000.5 60 2.3", "1001.5 80 2.1"])
    assert is_clean(w) and w.curves["GR"].values.tolist() == [50, 60, 70, 80]
    assert any("sorted" in n for n in w.notes)


def test_bottom_up_file_is_reversed_silently(tmp_path):
    w = write_las(tmp_path / "a.las", ["1001.5 80 2.1", "1001.0 70 2.2", "1000.5 60 2.3", "1000.0 50 2.4"])
    assert is_clean(w) and w.curves["GR"].values.tolist() == [50, 60, 70, 80]
    assert w.notes == []  # bottom-up order is normal, not a problem worth reporting


def test_null_markers_other_than_declared(tmp_path):
    w = write_las(tmp_path / "a.las", ["1000.0 50 2.4", "1000.5 -9999 2.3", "1001.0 -999.25 -999", "1001.5 80 2.1"])
    gr, rhob = w.curves["GR"].values, w.curves["RHOB"].values
    assert np.isnan(gr[1]) and np.isnan(gr[2]) and np.isnan(rhob[2])
    assert gr[0] == 50 and gr[3] == 80


def test_valid_999_values_are_kept(tmp_path):
    """999 and 9999 can be real depths or readings: only negative markers are nulls."""
    w = write_las(tmp_path / "a.las", ["999.0 999 2.4", "9999.0 50 2.3"])
    assert w.depth.tolist() == [999.0, 9999.0] and w.curves["GR"].values[0] == 999


def test_null_depth_rows_are_removed(tmp_path):
    w = write_las(tmp_path / "a.las", ["1000.0 50 2.4", "-999.25 60 2.3", "1001.0 70 2.2", "1001.5 80 2.1"])
    assert is_clean(w) and w.depth.tolist() == [1000.0, 1001.0, 1001.5]


@pytest.mark.parametrize(
    "rows",
    [
        ["1000.0 50 2.4", "1000.3 55 2.35", "1001.1 70 2.2"],  # STEP=0, irregular
        ["1000.0\t50\t2.4", "1000.5\t60\t2.3", "1001.0\t70\t2.2"],
    ],
)  # tabs
def test_irregular_and_tab_separated(tmp_path, rows):
    w = write_las(tmp_path / "a.las", rows, well=well_header(step="0"))
    assert is_clean(w) and w.curves["GR"].values[-1] == 70


def test_las12_well_name_in_description(tmp_path):
    w = write_las(
        tmp_path / "a.las",
        ["1000.0 50 2.4", "1000.5 60 2.3"],
        version="1.2",
        well=well_header(name=" WELL.  : POZO ESTE-7"),
    )
    assert w.name == "POZO ESTE-7"


def test_missing_well_name_uses_file_name(tmp_path):
    w = write_las(tmp_path / "sin_nombre.las", ["1000.0 50 2.4", "1000.5 60 2.3"], well=well_header(name=None))
    assert w.name == "sin_nombre"


def test_lowercase_feet_and_all_null_curve(tmp_path):
    curves = [" DEPT.ft : depth", " GR.GAPI : gamma", " RHOB.G/C3 : density"]
    w = write_las(
        tmp_path / "a.las", ["1000.0 -999.25 2.4", "1000.5 -999.25 2.3"], well=well_header(unit="ft"), curves=curves
    )
    assert w.depth_unit == "ft" and not w.curves["GR"].has_data


def test_only_null_depths_is_an_error(tmp_path):
    with pytest.raises(ValueError):
        write_las(tmp_path / "a.las", ["-999.25 50 2.4", "-999.25 60 2.3"])


def test_deep_well_depth_9999_25_is_kept(tmp_path):
    """9999.25 ft is a real depth in deep wells, not a null marker."""
    w = write_las(
        tmp_path / "a.las",
        ["9999.00 50 2.4", "9999.25 60 2.3", "9999.50 70 2.2"],
        well=well_header(unit="FT", null="-999.25"),
    )
    assert w.depth.tolist() == [9999.0, 9999.25, 9999.5] and w.notes == []
