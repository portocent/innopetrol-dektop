"""Plantillas en JSON: guardar, cargar y aplicar un layout a cualquier pozo.

Reemplaza las plantillas con pickle: JSON es legible, se puede editar a mano, no ejecuta
código al abrirlo y no se rompe cuando cambian las clases internas.
"""

from __future__ import annotations

import json
from pathlib import Path

from innopetrol.model.layout import LogLayout
from innopetrol.model.mnemonics import default_scale, family_of, resolve_curve

FORMAT = "innopetrol-template"
VERSION = 1
SUFFIX = ".ipt.json"


class TemplateError(Exception):
    pass


def template_to_json(layout: LogLayout) -> str:
    data = layout.to_dict()
    # Se guarda la familia de cada curva para poder encontrar su equivalente en otro pozo.
    for t in data["tracks"]:
        for c in t["curves"]:
            c["family"] = c.get("family") or family_of(c["mnemonic"])
    return json.dumps({"format": FORMAT, "version": VERSION, **data}, indent=2, ensure_ascii=False)


def template_from_json(text: str) -> LogLayout:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise TemplateError(f"el archivo no es JSON válido ({e.msg}, línea {e.lineno})") from e
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise TemplateError("el archivo no es una plantilla de InnoPetrol")
    if data.get("version", 0) > VERSION:
        raise TemplateError("la plantilla fue creada con una versión más nueva del programa")
    try:
        return LogLayout.from_dict(data)
    except (TypeError, ValueError, KeyError) as e:
        raise TemplateError(f"plantilla con formato inválido: {e}") from e


def save_template(path: str | Path, layout: LogLayout) -> None:
    Path(path).write_text(template_to_json(layout), encoding="utf-8")


def load_template(path: str | Path) -> LogLayout:
    return template_from_json(Path(path).read_text(encoding="utf-8"))


def apply_template(layout: LogLayout, well) -> tuple[LogLayout, list[str]]:
    """Adapta la plantilla al pozo. Devuelve (layout, curvas que no se encontraron).

    Las curvas que no existen en el pozo se quitan; los rellenos que dependían de ellas también.
    Escalas vacías (automáticas) se completan con la escala por defecto del pozo.
    """
    result = layout.copy()
    missing: list[str] = []
    for track in result.tracks:
        renamed: dict[str, str] = {}
        kept = []
        for c in track.curves:
            actual = resolve_curve(well, c)
            if actual is None:
                missing.append(c.mnemonic)
                continue
            renamed[c.mnemonic] = actual
            c.mnemonic = actual
            if c.left is None or c.right is None:
                left, right, log = default_scale(well, actual, c.family)
                c.left = left if c.left is None else c.left
                c.right = right if c.right is None else c.right
            kept.append(c)
        track.curves = kept
        fills = []
        for f in track.fills:
            ok = True
            for side in ("left_curve", "right_curve"):
                name = getattr(f, side)
                if name is not None:
                    if name in renamed:
                        setattr(f, side, renamed[name])
                    else:
                        ok = False
            if ok:
                fills.append(f)
        track.fills = fills
    return result, sorted(set(missing))
