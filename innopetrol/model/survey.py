"""Deviation surveys: true vertical depth (TVD) from measured depth by minimum curvature.

The wellbore between two survey stations is modeled as a circular arc (minimum curvature
method, the industry standard). Log samples between stations are placed exactly on that arc by
interpolating the direction vector (spherical linear interpolation), not by interpolating TVD
linearly.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from innopetrol.i18n import _

_MD_COLS = ("md", "measured depth", "depth", "dept", "prof", "profundidad", "md (m)", "md (ft)")
_INC_COLS = ("inc", "incl", "inclination", "inclinacion", "inclinación", "dev", "devi", "deviation", "angle")
_AZI_COLS = ("azi", "azim", "azimuth", "azimut", "az", "hazi", "dir", "direction")


class SurveyError(Exception):
    pass


@dataclass
class Survey:
    md: np.ndarray  # same depth unit as the well
    inc: np.ndarray  # degrees from vertical
    azi: np.ndarray  # degrees from north, clockwise
    tvd: np.ndarray = field(init=False)
    north: np.ndarray = field(init=False)
    east: np.ndarray = field(init=False)

    def __post_init__(self):
        md = np.asarray(self.md, dtype=float)
        inc = np.asarray(self.inc, dtype=float)
        azi = np.asarray(self.azi, dtype=float) % 360
        ok = np.isfinite(md) & np.isfinite(inc) & np.isfinite(azi)
        md, inc, azi = md[ok], inc[ok], azi[ok]
        order = np.argsort(md, kind="stable")
        md, inc, azi = md[order], inc[order], azi[order]
        keep = np.concatenate(([True], np.diff(md) > 0))
        md, inc, azi = md[keep], inc[keep], azi[keep]
        if md.size < 1:
            raise SurveyError(_("the survey has no valid stations"))
        if np.any((inc < 0) | (inc > 180)):
            raise SurveyError(_("inclinations must be between 0 and 180 degrees"))
        if md[0] > 0:
            # Tie-in at surface: vertical from MD 0 down to the first station.
            md, inc, azi = np.concatenate(([0.0], md)), np.concatenate(([0.0], inc)), np.concatenate(([azi[0]], azi))
        self.md, self.inc, self.azi = md, inc, azi
        self._t = _direction(inc, azi)
        self.north, self.east, self.tvd = _minimum_curvature(md, self._t)

    @property
    def max_inclination(self) -> float:
        return float(self.inc.max())

    def to_dict(self) -> dict:
        return {"md": self.md.tolist(), "inc": self.inc.tolist(), "azi": self.azi.tolist()}

    @classmethod
    def from_dict(cls, d: dict) -> Survey:
        return cls(np.asarray(d["md"], float), np.asarray(d["inc"], float), np.asarray(d["azi"], float))

    def position(self, md_query) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """(TVD, north, east) at arbitrary measured depths, exactly on the minimum-curvature arcs.

        Below the last station the last direction is extended in a straight line.
        """
        q = np.atleast_1d(np.asarray(md_query, dtype=float))
        out = np.full((q.size, 3), np.nan)
        valid = np.isfinite(q)
        qv = q[valid]
        seg = np.clip(np.searchsorted(self.md, qv, side="right") - 1, 0, self.md.size - 1)
        start = np.column_stack((self.north[seg], self.east[seg], self.tvd[seg]))
        t1 = self._t[seg]
        last = seg == self.md.size - 1
        nxt = np.minimum(seg + 1, self.md.size - 1)
        t2 = np.where(last[:, None], t1, self._t[nxt])
        seg_len = np.where(last, 1.0, self.md[nxt] - self.md[seg])
        s = qv - self.md[seg]  # distance along the hole from the segment start
        frac = np.where(last, 0.0, np.clip(s / seg_len, 0, 1))
        beta = _angle(t1, t2)  # dogleg of the whole segment
        tq = _slerp(t1, t2, frac, beta)  # direction at the query point
        disp = _arc_displacement(t1, tq, s, beta * frac)
        out[valid] = start + disp
        return out[:, 2], out[:, 0], out[:, 1]

    def tvd_at(self, md_query) -> np.ndarray:
        return self.position(md_query)[0]


def _direction(inc_deg, azi_deg) -> np.ndarray:
    """Unit tangent vectors (north, east, down)."""
    i, a = np.radians(inc_deg), np.radians(azi_deg)
    return np.column_stack((np.sin(i) * np.cos(a), np.sin(i) * np.sin(a), np.cos(i)))


def _angle(t1: np.ndarray, t2: np.ndarray) -> np.ndarray:
    dot = np.clip(np.sum(t1 * t2, axis=-1), -1.0, 1.0)
    return np.arccos(dot)


def _ratio_factor(beta: np.ndarray) -> np.ndarray:
    """Minimum-curvature ratio factor 2/β·tan(β/2), → 1 for straight segments."""
    beta = np.asarray(beta, dtype=float)
    out = np.ones_like(beta)
    big = beta > 1e-7
    out[big] = 2.0 / beta[big] * np.tan(beta[big] / 2.0)
    return out


def _arc_displacement(t1, t2, length, beta) -> np.ndarray:
    """Displacement along a circular arc of the given length joining directions t1 and t2."""
    return (np.asarray(length)[:, None] / 2.0) * (t1 + t2) * _ratio_factor(beta)[:, None]


def _slerp(t1, t2, frac, beta) -> np.ndarray:
    """Direction at a fraction of the arc between t1 and t2 (spherical linear interpolation)."""
    frac = np.asarray(frac, dtype=float)[:, None]
    beta = np.asarray(beta, dtype=float)[:, None]
    small = beta < 1e-7
    sin_b = np.where(small, 1.0, np.sin(beta))
    a = np.where(small, 1 - frac, np.sin((1 - frac) * beta) / sin_b)
    b = np.where(small, frac, np.sin(frac * beta) / sin_b)
    t = a * t1 + b * t2
    return t / np.linalg.norm(t, axis=1, keepdims=True)


def _minimum_curvature(md: np.ndarray, t: np.ndarray):
    n = md.size
    pos = np.zeros((n, 3))
    if n > 1:
        d_md = np.diff(md)
        beta = _angle(t[:-1], t[1:])
        steps = _arc_displacement(t[:-1], t[1:], d_md, beta)
        pos[1:] = np.cumsum(steps, axis=0)
    return pos[:, 0], pos[:, 1], pos[:, 2]


def load_survey_csv(path: str | Path) -> Survey:
    """Reads MD / inclination / azimuth columns from a CSV or text file (any common delimiter).

    Headers are recognized in English and Spanish; without a header the first three numeric
    columns are taken as MD, inclination and azimuth.
    """
    text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if not lines:
        raise SurveyError(_("the file is empty"))
    try:
        dialect = csv.Sniffer().sniff("\n".join(lines[:20]), delimiters=",;\t ")
    except csv.Error:
        dialect = csv.excel
    rows = [[c.strip() for c in r if c.strip()] for r in csv.reader(lines, dialect)]
    head = [c.lower() for c in rows[0]]
    if not _is_number(rows[0][0]):
        md_i, inc_i, azi_i = (_find(head, _MD_COLS), _find(head, _INC_COLS), _find(head, _AZI_COLS))
        if None in (md_i, inc_i, azi_i):
            raise SurveyError(
                _("could not find MD, inclination and azimuth columns in the header: {header}").format(
                    header=", ".join(rows[0])
                )
            )
        rows = rows[1:]
    else:
        md_i, inc_i, azi_i = 0, 1, 2
    data = []
    for r in rows:
        try:
            data.append([_to_float(r[md_i]), _to_float(r[inc_i]), _to_float(r[azi_i])])
        except (ValueError, IndexError):
            continue  # unit rows, comments, totals…
    if not data:
        raise SurveyError(_("no numeric survey stations were found"))
    arr = np.asarray(data)
    return Survey(arr[:, 0], arr[:, 1], arr[:, 2])


def _find(head: list[str], names: tuple) -> int | None:
    for i, h in enumerate(head):
        base = h.split("(")[0].split("[")[0].strip()
        if h in names or base in names:
            return i
    return None


def _to_float(s: str) -> float:
    return float(s.replace(",", ".")) if s.count(",") == 1 and "." not in s else float(s)


def _is_number(s: str) -> bool:
    try:
        _to_float(s)
        return True
    except ValueError:
        return False
