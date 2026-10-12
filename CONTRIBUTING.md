# Contributing to InnoPetrol

Thanks for helping. This guide covers setting up, the conventions, and step-by-step recipes for the
most common changes. Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) first: it explains the layers and
the invariants the code relies on.

## Setup

Requirements: Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                          # program + development tools
uv run pre-commit install        # lint and format before every commit (once per clone)
uv run python -m innopetrol samples/Testdata.las
```

## Checks (the same ones CI runs)

```bash
uv run pytest                    # tests (offscreen: no windows open)
uv run pytest --cov              # with coverage
uv run ruff check                # lint
uv run ruff format               # format (line length 120)
uv run mypy                      # types
```

A change is ready when all of them pass. Bug fixes come with a test that failed before the fix.

## Conventions

**Code**
- **Language:** code, identifiers, comments and docstrings are in English.
- **Comments:** they explain *why*. The code should already say *what*.
- **Size:** keep functions short. ruff fails above complexity 12 or 60 statements, which usually means
  splitting into named steps (see `petro._Builder` or `painter._header_*`).
- **Reuse:** look in `ui/widgets.py`, `model/text_tables.py`, `model/units.py` and
  `render/painter.py` (`map_values`, `polygon_from_arrays`) before writing a new helper.
- **Layers:** `model` must not import Qt.

**Interface texts (i18n)**
- **Mark every text:** wrap visible texts with `_()` from `innopetrol.i18n`. Module-level constants use
  `N_()` and are translated when shown (`_(FAMILY.name)`).
- **Placeholders:** use named ones, never f-strings inside `_()`:
  `_("Curves not found in {well}").format(well=name)`.
- **Whole sentences:** a sentence built from pieces cannot be translated well.
- **`_` is reserved:** never use it as a throwaway variable (`for _i in …`, `path, _filter = …`). It
  would hide the translation function, and a test checks for this.
- **After changing texts:** run `uv run python tools/i18n.py update`, translate the new entries in
  `innopetrol/locale/es/LC_MESSAGES/innopetrol.po`, then `uv run python tools/i18n.py compile`. The tests
  fail if a text is untranslated or the `.mo` is stale.

**Changes to a well**
- **Undo:** changes the user should be able to undo go through `WellDocument` methods or inside
  `with doc.undo_step(_("What it does")):`. Code that edits `doc.layout` in place must emit
  `doc.layoutChanged`.
- **View settings:** depth reference and units are applied with `_untracked()` and are not undoable.

**Commits**
- **One topic per commit.** The subject line is short, in the imperative mood ("Add …", "Fix …").
- **Mechanical changes** go in their own commit (formatting, renames). Add pure-formatting commits to
  `.git-blame-ignore-revs`.

## Recipes

### Recognize a new curve name

If it is a new name for an existing family (a company's own GR mnemonic, for example), users can add
it themselves in *Template ▸ Mnemonic aliases…*. To make it built-in, add it to the family's aliases
in `innopetrol/model/mnemonics.py` (`FAMILIES`).

To add a new family:
1. Add a `Family(key, N_("Name"), aliases, left, right, log, color)` to `FAMILIES`.
2. If its default scale has a unit, add the family to `_FAMILY_UNITS`.
3. If it belongs in the automatic layout, add it to a group in `_GROUPS`.
4. Add a test in `tests/test_mnemonics_template.py`, then update the translations.

### Add a track kind

`TrackSpec.kind` is `"curves"`, `"depth"` or `"volumes"`. For a new kind (core points, intervals…):
1. **Model:** add the kind and any fields it needs in `model/layout.py`. Fields must have defaults:
   old layouts must still load, and `_known` ignores unknown keys.
2. **Body:** in `render/painter.py`, branch in `draw_track_body` and write a `_draw_<kind>` function.
3. **Header:** add a `_header_<kind>` function and its height in `header_height`.
4. **Creation and editing:** offer it in `WellView.add_track` and the context menu, and adapt the
   track editor if it needs other columns.
5. **Tests:** render a small image in `tests/test_presentation.py` and check pixels, as the volumes
   test does.

### Add a petrophysical model

Example: a new water saturation equation.
1. **Reference function:** write it in NumPy in `model/petro.py` next to `sw_archie`. It documents
   the equation and is what the tests compare against.
2. **Name:** add it to `SW_MODELS` with `N_()`.
3. **Formula:** in `_Builder.saturation`, write it as a calculator expression using the result names
   (`PHIE`, `VSH`), the parameters (`self.param("rw")`, which handles values by zone) and the input
   references.
4. **Tests:** compare it with the reference function on `samples/Testdata.las` in
   `tests/test_petro_models.py`. Check its limiting case too (e.g. it equals Archie when Vsh = 0).
5. **References:** add the bibliographic reference to the module docstring.

### Add a language

```bash
uv run python tools/i18n.py init fr       # creates innopetrol/locale/fr/LC_MESSAGES/innopetrol.po
# translate the .po (Poedit or a text editor), then:
uv run python tools/i18n.py compile
```

Then add the language to `LANGUAGES` in `innopetrol/i18n.py`.

### Add an action to the main window

1. **Action:** create it in `MainWindow._build_actions` with `self._action(slot, shortcut)`. Pass
   `needs_doc=False` if it works without an open well.
2. **Placement:** add it to a menu in `_build_menus` (and to the toolbar if it is frequent).
3. **Texts:** set them in `retranslate()`, so the language can change at runtime.
4. **Undo:** if it changes a well, use `doc.undo_step` (see above).

## Verifying drawing changes

Rendering is checked by tests, but small visual regressions are easy to miss:
- **Refactors:** export a few PNGs (`render.export.export_png`) before and after and compare them
  pixel by pixel. They must be identical.
- **Visual changes:** look at the images, and include a screenshot in the pull request.
- **Performance:** follow the notes on performance-critical code in
  [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
