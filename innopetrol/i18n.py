"""Interface translations (gettext).

Source strings are written in English and marked with ``_()``. Translations live in
``innopetrol/locale/<lang>/LC_MESSAGES/innopetrol.po`` (compiled to ``.mo``). Lookups happen on
every call, so switching the language at runtime affects every string built afterwards.

Rules for translatable strings:
- use named placeholders: ``_("Could not open {name}").format(name=...)``, never f-strings inside ``_()``;
- translate whole sentences, never concatenate translated fragments;
- module-level constants are marked with ``N_()`` and translated with ``_()`` when displayed.
"""

from __future__ import annotations

import gettext
import locale
from pathlib import Path

DOMAIN = "innopetrol"
LOCALE_DIR = Path(__file__).resolve().parent / "locale"
LANGUAGES = {"en": "English", "es": "Español"}  # adding a language = adding its .po file
DEFAULT = "en"

_translation: gettext.NullTranslations = gettext.NullTranslations()
_current = DEFAULT
_qt_translators: list = []


def _(message: str) -> str:
    return _translation.gettext(message)


def ngettext(singular: str, plural: str, n: int) -> str:
    return _translation.ngettext(singular, plural, n)


def pgettext(context: str, message: str) -> str:
    """Translation with a context, for short words that translate differently depending on use."""
    return _translation.pgettext(context, message)


def N_(message: str) -> str:
    """Marks a string for extraction without translating it yet."""
    return message


def current_language() -> str:
    return _current


def set_language(code: str) -> str:
    """Activates a language (falls back to English if it is unknown). Returns the active code."""
    global _translation, _current
    code = code if code in LANGUAGES else DEFAULT
    if code == DEFAULT:
        _translation = gettext.NullTranslations()
    else:
        _translation = gettext.translation(DOMAIN, LOCALE_DIR, languages=[code], fallback=True)
    _current = code
    return code


def system_language() -> str:
    """Language of the operating system if a catalog exists for it, otherwise English."""
    candidates = []
    try:
        from PySide6.QtCore import QLocale

        candidates += QLocale.system().uiLanguages()
    except ImportError:
        pass
    lang, _enc = locale.getlocale()
    if lang:
        candidates.append(lang)
    for c in candidates:
        code = c.replace("-", "_").split("_")[0].lower()
        if code in LANGUAGES:
            return code
    return DEFAULT


def install_qt_translator(app, code: str) -> None:
    """Translates Qt's own dialogs (Yes/No/Cancel buttons, file dialogs) with the bundled qtbase .qm."""
    from PySide6.QtCore import QLibraryInfo, QTranslator

    for t in _qt_translators:
        app.removeTranslator(t)
    _qt_translators.clear()
    if code == DEFAULT:
        return
    translator = QTranslator(app)
    if translator.load(f"qtbase_{code}", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
        _qt_translators.append(translator)
