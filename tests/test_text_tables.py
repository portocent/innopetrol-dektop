"""Delimited text tables shared by the tops and survey readers."""

import pytest

from innopetrol.model.text_tables import find_column, is_number, parse_number, read_rows


@pytest.mark.parametrize("text, value", [("1.5", 1.5), ("1,5", 1.5), (" -12 ", -12.0), ("1e3", 1000.0)])
def test_parse_number(text, value):
    assert parse_number(text) == value


def test_is_number():
    assert is_number("2,75") and not is_number("MD") and not is_number("")


def test_find_column_ignores_case_and_units():
    header = ["Well", "Profundidad (m)", "Name [-]"]
    assert find_column(header, ("profundidad", "depth")) == 1
    assert find_column(header, ("name",)) == 2
    assert find_column(header, ("azimuth",)) is None


@pytest.mark.parametrize("sep", [",", ";", "\t"])
def test_read_rows_guesses_the_separator(tmp_path, sep):
    p = tmp_path / "t.csv"
    p.write_text(
        f"name{sep}depth\n\nA{sep}1000\nB{sep}1100,5\n".replace(",5", ".5")
        if sep == ","
        else f"name{sep}depth\n\nA{sep}1000\nB{sep}1100,5\n",
        encoding="utf-8",
    )
    rows = read_rows(p)
    assert rows[0] == ["name", "depth"] and rows[1] == ["A", "1000"] and len(rows) == 3


def test_read_rows_aligned_with_spaces_and_comments(tmp_path):
    p = tmp_path / "s.txt"
    p.write_text("# exported survey\nMD    INC   AZI\n0     0     0\n1000  12.5  45\n", encoding="utf-8")
    rows = read_rows(p, delimiters=",;\t ", skip_comments=True, drop_empty_cells=True)
    assert rows == [["MD", "INC", "AZI"], ["0", "0", "0"], ["1000", "12.5", "45"]]
