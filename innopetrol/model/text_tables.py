"""Reading delimited text tables (CSV/TXT exported from spreadsheets and other programs).

Shared by the tops and survey readers: separator detection, columns found by header name in
English or Spanish (ignoring a unit suffix such as "MD (m)") and numbers with a decimal comma.
"""

from __future__ import annotations

import csv
from pathlib import Path


def read_rows(
    path: str | Path, delimiters: str = ",;\t", skip_comments: bool = False, drop_empty_cells: bool = False
) -> list[list[str]]:
    """Non-empty rows of a text table, with the separator guessed from the first lines.

    `drop_empty_cells` suits files aligned with several spaces; `skip_comments` drops lines
    starting with '#'.
    """
    text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if skip_comments:
        lines = [ln for ln in lines if not ln.lstrip().startswith("#")]
    if not lines:
        return []
    try:
        dialect: type[csv.Dialect] | csv.Dialect = csv.Sniffer().sniff("\n".join(lines[:20]), delimiters=delimiters)
    except csv.Error:
        dialect = csv.excel
    rows = [[c.strip() for c in r] for r in csv.reader(lines, dialect)]
    if " " in delimiters and all(len(r) <= 1 for r in rows):
        # Columns aligned with a varying number of spaces: the sniffer cannot pick a single separator.
        rows = [ln.split() for ln in lines]
    if drop_empty_cells:
        rows = [[c for c in r if c] for r in rows]
    return [r for r in rows if any(r)]


def find_column(header: list[str], names: tuple[str, ...]) -> int | None:
    """Index of the first header cell matching one of `names` (case-insensitive, unit suffix ignored)."""
    for i, cell in enumerate(header):
        h = cell.strip().lower()
        base = h.split("(")[0].split("[")[0].strip()
        if h in names or base in names:
            return i
    return None


def parse_number(text: str) -> float:
    """A number written with a decimal point or a decimal comma ("1.5", "1,5"). Raises ValueError."""
    s = text.strip()
    if s.count(",") == 1 and "." not in s:
        s = s.replace(",", ".")
    return float(s)


def is_number(text: str) -> bool:
    try:
        parse_number(text)
    except ValueError:
        return False
    return True
