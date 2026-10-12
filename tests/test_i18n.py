"""Localization: catalog completeness, placeholders, runtime switching and gettext pitfalls."""

import ast
import gettext
import io
import re
from pathlib import Path

import pytest
from babel.messages.extract import extract_from_dir
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po
from PySide6.QtCore import QSettings

from innopetrol import i18n

PACKAGE = Path(i18n.__file__).parent
PO = PACKAGE / "locale" / "es" / "LC_MESSAGES" / "innopetrol.po"
MO = PO.with_suffix(".mo")
KEYWORDS = {"_": None, "N_": None, "ngettext": (1, 2), "pgettext": ((1, "c"), 2)}
PLACEHOLDER = re.compile(r"{[a-z_]*}")


def _catalog():
    return read_po(PO.open("rb"), locale="es")


def _code_messages():
    out = set()
    for _filename, _lineno, message, _comments, context in extract_from_dir(str(PACKAGE), keywords=KEYWORDS):
        msgid = message if isinstance(message, str) else message[0]
        out.add((context, msgid))
    return out


def test_every_string_in_the_code_is_translated():
    catalog = _catalog()
    missing = []
    for context, msgid in sorted(_code_messages(), key=str):
        m = catalog.get(msgid, context=context)
        if m is None or not m.string or m.fuzzy or (isinstance(m.string, tuple) and not all(m.string)):
            missing.append(msgid)
    assert not missing, "untranslated (run tools/i18n.py update): " + ", ".join(missing[:10])


def test_compiled_catalog_is_up_to_date():
    """The shipped .mo must match the .po (catches forgetting `tools/i18n.py compile`)."""
    buf = io.BytesIO()
    write_mo(buf, _catalog())
    buf.seek(0)
    fresh = gettext.GNUTranslations(buf)._catalog
    shipped = gettext.GNUTranslations(MO.open("rb"))._catalog
    fresh.pop("", None)
    shipped.pop("", None)
    assert fresh == shipped


def test_placeholders_are_preserved():
    problems = []
    for m in _catalog():
        if not m.id:
            continue
        ids = m.id if isinstance(m.id, tuple) else (m.id,)
        strings = m.string if isinstance(m.string, tuple) else (m.string,)
        expected = set(PLACEHOLDER.findall(ids[-1]))
        for s in strings:
            if set(PLACEHOLDER.findall(s)) != expected:
                problems.append(ids[0])
    assert not problems, problems


def test_unknown_language_falls_back_to_english():
    assert i18n.set_language("xx") == "en"
    assert i18n._("Fit to window") == "Fit to window"


def test_model_messages_follow_the_language():
    from innopetrol.model.calculator import CalculatorError, evaluate
    from innopetrol.model.mnemonics import build_triple_combo
    from innopetrol.model.well import Well

    i18n.set_language("es")
    with pytest.raises(CalculatorError, match="curva desconocida"):
        evaluate("FOO + 1", {"A": [1.0]})
    well = Well.from_las(Path(__file__).parent.parent / "samples" / "Testdata.las")
    assert [t.title for t in build_triple_combo(well).tracks][:2] == ["Correlación", "Prof."]
    i18n.set_language("en")
    assert [t.title for t in build_triple_combo(well).tracks][:2] == ["Correlation", "Depth"]


def test_live_language_switch(qtbot, tmp_path, samples):
    from innopetrol.ui.main_window import MainWindow

    settings = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    w = MainWindow(settings)
    qtbot.addWidget(w)
    w.open_las([str(samples / "Testdata.las")])
    assert w.m_file.title() == "&File" and w.a_zoom_in.text() == "Zoom in"
    w.set_language("es")
    assert w.m_file.title() == "&Archivo"
    assert w.a_zoom_in.text() == "Acercar" and w.a_fit.iconText() == "Ajustar"
    assert w.dock.windowTitle() == "Pozos"
    assert w.tree.template_item.text(0).startswith("Plantilla por defecto")
    assert w.language_actions["es"].isChecked()
    # The choice is remembered for the next start
    w2 = MainWindow(settings)
    qtbot.addWidget(w2)
    assert w2.m_file.title() == "&Archivo"
    w2.set_language("en")
    assert w2.m_file.title() == "&File"
    w.dirty = w2.dirty = False


def test_underscore_is_never_shadowed():
    """`_` is the translation function: using it as a throwaway variable silently breaks texts."""
    offenders = []
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                names.append(node.id)
            elif isinstance(node, ast.arg):
                names.append(node.arg)
            if "_" in names:
                offenders.append(f"{path.relative_to(PACKAGE)}:{node.lineno}")
    assert not offenders, offenders
