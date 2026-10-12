# Architecture

This document explains how InnoPetrol is organized and the rules that keep it correct. Read it before
changing code. For setting up and contributing, see [CONTRIBUTING.md](../CONTRIBUTING.md).

## Layers

```
innopetrol/
  model/    pure Python + NumPy: data, units, calculations, file formats. No Qt.
  render/   QPainter drawing of logs, shared by the screen and the PDF/PNG export.
  ui/       PySide6 windows, dialogs and widgets.
  i18n.py   interface translations (gettext).  errors.py  error log and error dialog.
```

Dependencies only go downwards: `ui` → `render` → `model`. `model` never imports Qt, and neither
`model` nor `render` imports `ui`. This keeps calculations testable without a GUI and lets the export
draw exactly what the screen shows.

## Data flow

```
LAS / DLIS file ──► model.io.load_well ──► Well (depth in MD, curves in file units, tops in MD)
                                              │
                         WellDocument (ui/document.py): Well + LogLayout + petrophysics
                         parameters + display settings + undo history; Qt signals
                                              │
                         DepthView (model/depth_view.py): the well as drawn
                         (MD/TVD/TVDSS, m/ft, curve display units). Read-only.
                                              │
           render.scene.paint_log ──► painter.draw_track_body / draw_track_header
                │                                          │
     ui.LogCanvas (screen, tile cache)           render.export (PDF / PNG at scale)
```

### Wells in a project

A project can hold hundreds of wells, so a well has three states:

1. **In the project:** a `WellRef` (`model/catalog.py`) with the file path and a `WellSummary`
   (name, depth range, curves, location…). Nothing is read from the file; while the well is not
   loaded, the `WellRef` keeps its project entry and `save_project` writes it back unchanged.
2. **Loaded:** it has a `WellDocument`. `ui/project_wells.ProjectWells` keeps every `WellRef` and the
   documents of the loaded ones; `ensure_loaded` loads wells on demand (with progress for many).
3. **Shown:** it also has a window (`MainWindow.views`). Closing the window keeps the well loaded.

`MainWindow.docs` are the loaded wells. Projects store each well's summary and whether its window was
open; opening a project loads only those wells. A well added from a folder (`refs_from_file`) has no
layout until it is first loaded, when it gets the default template.

Well files can be copied next to the project (`catalog.copy_files` into `data_folder`, named
`<project>_pozos/` in any language) and found again by file name when moved (`catalog.relocate`).
Paths in a `WellRef` are kept resolved, so finding duplicates is a plain comparison.

### Invariants

Never break these.

1. **Stored data never changes for display.**
   - Depths are always measured depth (MD) in the file's depth unit.
   - Curves keep the file's units, and tops are stored in MD.
   - Choosing TVD, meters or kg/m³ only changes the `DepthView` that drawing code receives.
   - Converting from display back to storage uses `DepthView.to_md`.
2. **Calculations convert their inputs explicitly.**
   - Petrophysics formulas include the conversions they need, e.g. `(RHOB * 0.001)` for a density
     stored in kg/m³ (`petro.input_ref`).
   - Results therefore never depend on how a file labels its units.
   - `mnemonics.data_unit` also checks the values, catching porosity in % labeled as "DEC".
3. **Computed curves are formulas.**
   - Every computed curve keeps the calculator expression that produced it.
   - Projects store the formula, not the values, and recompute it on load.
   - Formulas may use `DEPTH` and `TVD` (`Well.formula_env`).
4. **Undo works by snapshots** (`ui/document.py`).
   - After any change signal (`layoutChanged`, `curvesChanged`, `topsChanged`), the document compares
     its content with the previous state and pushes a step to its `QUndoStack`.
   - Content means layout, tops, curves, petrophysics parameters, survey and location. Curves are
     shared by reference, never copied.
   - View settings (depth reference, units) are not undone. They are applied inside `_untracked()`.
   - Group a multi-step operation with `with doc.undo_step(_("Name")):`.
   - Code that edits `doc.layout` in place must emit `doc.layoutChanged` afterwards.
5. **Layout scales record their unit.**
   - `CurveStyle.unit` is the unit the left/right values are written in.
   - `WellDocument.adopt_layout` converts any layout (template, restored snapshot, new result tracks) to
     the units the curves are displayed in.

## Main modules

| Module | Responsibility |
|---|---|
| `model/well.py` | `Well`, `Curve`; LAS reading with fixes for real-world files (nulls, duplicated depths). |
| `model/dlis.py` | DLIS reading with dlisio (one well per depth frame). |
| `model/units.py` | Unit spellings, conversions, unit systems. |
| `model/mnemonics.py` | Curve families (gamma ray, density…), aliases (`AliasRegistry`, user-editable), default styles, Triple Combo and volumes tracks. |
| `model/depth_view.py` | The display view of a well (reference, units). |
| `model/survey.py` | Minimum-curvature survey, TVD at any MD. |
| `model/calculator.py` | Safe expression evaluator (AST, closed list of operations; no `eval`). |
| `model/petro.py` | Petrophysics as formulas, built in ordered steps; zone parameters; zone summary. |
| `model/petro_layout.py` | Result tracks and where to place them. |
| `model/equations.py` | Every equation with its variables, validity and bibliographic reference (shown in the program). |
| `model/workbook.py` | Excel output: tables and the verification workbook (the equations as spreadsheet formulas). |
| `model/layout.py`, `template.py`, `project.py` | Layout dataclasses and their JSON files. |
| `model/catalog.py` | `WellRef` and `WellSummary`: the wells of a project without their data; header-only reading. |
| `render/painter.py` | Drawing of track bodies and headers (curves, backup scales, fills, color maps, volumes, tops). |
| `render/export.py` | PNG and paginated PDF with the log heading. |
| `ui/main_window.py` | Composition root: menus, actions, opening wells, launching tools. |
| `ui/session.py` | Project file, unsaved changes, recent files, autosave and recovery (no widgets). |
| `ui/log_canvas.py` | Interactive log with tile cache and adaptive previews. |
| `ui/document.py` | `WellDocument`: state of a loaded well, signals, undo. |
| `ui/project_wells.py` | `ProjectWells`: the project's wells, loading and unloading them. |

## Validation

- **Reference cases:** `tests/test_reference_cases.py` holds results worked out by hand from the
  published equations.
- **Independent recalculation:** `tests/test_workbook.py` evaluates the verification workbook's formulas
  with pycel, a spreadsheet engine independent of InnoPetrol.
- **Real files:** `tests/test_realdata.py` and `tools/realdata.py` run the program over ~1500 real LAS
  files.
- **No third-party data in the repository:** real files are downloaded to `~/.cache/innopetrol`, or
  read from a folder you choose. Every problem found in them becomes a small synthetic test in
  `tests/test_las_quirks.py`.

## Performance-critical code

Do not change it without measuring before and after.

- **`render/painter.py`:**
  - `_draw_curve` / `_stroke` draw dense curves as one min/max span per pixel row (`_envelope`).
  - Polygons are filled from NumPy without Python loops (`_qpolygon`, `polygon_from_arrays`).
  - Color-map fills sample one value per pixel row and merge rows of the same color.
- **`ui/log_canvas.py` and `ui/tile_cache.py`:**
  - The body is drawn in 256-px tiles that are reused while scrolling.
  - The cursor repaints only its strip.
  - On slow machines, gestures show previews (`frame_cost_ms`).
- **`model/survey.py`:** vectorized minimum curvature and slerp.

What to watch for:
- Keep NumPy operations vectorized, and avoid creating Qt objects per sample.
- To verify a refactor, export reference PNGs before and after and compare them pixel by pixel, and
  time a full redraw of a `LogCanvas`.

## User interface conventions

- **Language:** code, comments and docstrings are in English. Every visible text goes through `_()`.
  See the i18n rules in CONTRIBUTING.
- **Labels:** dialogs build their widgets in `_build_*` methods and wire signals in `_connect_*`.
  Visible texts that can change language at runtime are set in `retranslate()` (main window).
- **Shared widgets:** `ui/widgets.py` provides `spin`, `choice_combo`, `curve_combo`,
  `fill_zone_combo`, `row_of`, `parse_float` and `key_text`. Use them instead of writing new helpers.
- **Long-lived windows:** non-modal windows are kept alive through `MainWindow._modeless`.
- **Settings:** stored with `QSettings`. Tests always pass a temporary `.ini` file, so they never touch
  the user's real settings or data folder.
