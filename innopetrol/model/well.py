"""Carga de archivos LAS y representación de un pozo."""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path

import lasio
import numpy as np

from innopetrol.model.tops import Top

FEET_UNITS = {"F", "FT", "FEET", "FOOT", "FT.", "FEET."}


@dataclass
class Curve:
    mnemonic: str
    unit: str
    description: str
    values: np.ndarray
    formula: str | None = None  # curvas calculadas guardan su fórmula para poder reproducirlas

    @property
    def has_data(self) -> bool:
        return bool(np.isfinite(self.values).any())

    @property
    def min(self) -> float:
        return float(np.nanmin(self.values)) if self.has_data else float("nan")

    @property
    def max(self) -> float:
        return float(np.nanmax(self.values)) if self.has_data else float("nan")


@dataclass
class HeaderItem:
    mnemonic: str
    unit: str
    value: str
    description: str


@dataclass
class Well:
    name: str
    path: Path | None
    depth: np.ndarray
    depth_unit: str  # "ft" o "m"
    depth_mnemonic: str = "DEPT"
    header: list[HeaderItem] = field(default_factory=list)
    curves: dict[str, Curve] = field(default_factory=dict)
    tops: list[Top] = field(default_factory=list)

    @classmethod
    def from_las(cls, path: str | Path) -> Well:
        path = Path(path)
        # lasio avisa por logging cuando cambia de motor para archivos WRAP=YES; no es un error.
        logging.getLogger("lasio").setLevel(logging.ERROR)
        las = lasio.read(str(path), encoding=detect_encoding(path), ignore_header_errors=True)
        if not las.curves:
            raise ValueError("el archivo no contiene curvas")
        depth = np.asarray(las.index, dtype=float)
        if depth.size < 2:
            raise ValueError("el archivo no contiene datos")

        unit_raw = (las.curves[0].unit or "").strip().upper()
        if not unit_raw and "STRT" in las.well:
            unit_raw = (las.well["STRT"].unit or "").strip().upper()
        depth_unit = "ft" if unit_raw in FEET_UNITS else "m"

        header = [
            HeaderItem(i.mnemonic, i.unit or "", str(i.value), i.descr or "") for i in las.well
        ]
        name = str(las.well["WELL"].value).strip() if "WELL" in las.well else ""
        curves = {}
        for c in las.curves[1:]:
            mnem = _unique(c.mnemonic.strip() or "CURVE", curves)
            curves[mnem] = Curve(mnem, (c.unit or "").strip(), (c.descr or "").strip(),
                                 np.asarray(c.data, dtype=float))

        # El dibujo asume profundidad creciente; algunos LAS vienen de fondo a superficie.
        if depth[0] > depth[-1]:
            depth = depth[::-1].copy()
            for c in curves.values():
                c.values = c.values[::-1].copy()

        return cls(
            name=name or path.stem,
            path=path,
            depth=depth,
            depth_unit=depth_unit,
            depth_mnemonic=las.curves[0].mnemonic,
            header=header,
            curves=curves,
        )

    @property
    def start(self) -> float:
        return float(self.depth[0])

    @property
    def stop(self) -> float:
        return float(self.depth[-1])

    @property
    def step(self) -> float:
        return float(np.median(np.diff(self.depth)))

    def header_value(self, mnemonic: str) -> str:
        for h in self.header:
            if h.mnemonic.upper() == mnemonic.upper():
                return h.value
        return ""

    def add_curve(self, curve: Curve, replace: bool = True) -> None:
        if curve.values.shape != self.depth.shape:
            raise ValueError("la curva no tiene el mismo número de muestras que la profundidad")
        if not replace and curve.mnemonic in self.curves:
            raise ValueError(f"ya existe una curva llamada {curve.mnemonic}")
        self.curves[curve.mnemonic] = curve

    def remove_curve(self, mnemonic: str) -> None:
        self.curves.pop(mnemonic, None)

    def value_at(self, mnemonic: str, depth: float) -> float:
        """Valor interpolado de una curva en una profundidad (NaN fuera de rango o en huecos)."""
        curve = self.curves.get(mnemonic)
        if curve is None or depth < self.start or depth > self.stop:
            return float("nan")
        i = int(np.searchsorted(self.depth, depth))
        if i == 0:
            return float(curve.values[0])
        d0, d1 = self.depth[i - 1], self.depth[i]
        v0, v1 = curve.values[i - 1], curve.values[i]
        t = 0.0 if d1 == d0 else (depth - d0) / (d1 - d0)
        return float(v0 + (v1 - v0) * t)

    def interval_mask(self, top: float | None, base: float | None) -> np.ndarray:
        mask = np.ones(self.depth.shape, dtype=bool)
        if top is not None:
            mask &= self.depth >= top
        if base is not None:
            mask &= self.depth < base
        return mask

    def to_las(self, path: str | Path, mask: np.ndarray | None = None) -> None:
        las = lasio.LASFile()
        for h in self.header:
            if h.mnemonic.upper() in ("STRT", "STOP", "STEP"):
                continue
            las.well[h.mnemonic] = lasio.HeaderItem(h.mnemonic, h.unit, h.value, h.description)
        sel = slice(None) if mask is None else mask
        unit = "FT" if self.depth_unit == "ft" else "M"
        las.append_curve(self.depth_mnemonic, self.depth[sel], unit=unit, descr="Depth")
        for c in self.curves.values():
            descr = c.description if c.formula is None else f"{c.description} [= {c.formula}]"
            las.append_curve(c.mnemonic, c.values[sel], unit=c.unit, descr=descr)
        las.well["WELL"] = lasio.HeaderItem("WELL", "", self.name, "WELL")
        # Codificación explícita: en Windows Python usaría cp1252 y fallaría con caracteres como φ.
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            las.write(f, version=2.0, fmt="%.5f")

    def to_csv(self, path: str | Path, mask: np.ndarray | None = None) -> None:
        sel = slice(None) if mask is None else mask
        names = [self.depth_mnemonic] + list(self.curves)
        columns = np.column_stack([self.depth[sel]] + [c.values[sel] for c in self.curves.values()])
        # utf-8-sig agrega el BOM que Excel en Windows necesita para mostrar bien los acentos.
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(names)
            for row in columns:
                writer.writerow(["" if np.isnan(v) else f"{v:.5f}" for v in row])


def detect_encoding(path: str | Path) -> str:
    """Codificación de un archivo de texto: UTF-8 (con o sin BOM), Windows-1252 o Latin-1.

    Muchos LAS de compañías latinoamericanas vienen en Windows-1252 ("Compañía"); otros en UTF-8.
    Sin esta detección lasio leería un UTF-8 como Windows-1252 y mostraría "CompaÃ±Ã­a".
    """
    raw = Path(path).read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    for enc in ("utf-8", "cp1252"):
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"  # decodifica cualquier byte


def _unique(name: str, existing: dict) -> str:
    if name not in existing:
        return name
    n = 2
    while f"{name}_{n}" in existing:
        n += 1
    return f"{name}_{n}"
