# Roadmap: from viewer to a tool engineers use daily

InnoPetrol already reads LAS 2.0, builds an automatic Triple Combo layout and supports true vertical
scales, fills, tops, basic petrophysics (Vsh, φ, Archie Sw, net pay), crossplots, multi-well
correlation, templates, projects, PDF/PNG/LAS export, English/Spanish UI and executables for Windows,
Linux and macOS.

Engineers adopt a viewer when **(1)** it opens *their* data, **(2)** they trust its numbers and
**(3)** the daily workflow is faster than the alternative (spreadsheets, commercial suites, or the free
viewers from service companies). This document lists what is missing, ordered by impact.
Items marked **[checked]** were verified in the code.

## A. Blockers: needed before use on a real project

1. **Data formats.** Only LAS 2.0 today.
   - **DLIS / LIS**: most modern service-company data is delivered as DLIS; LAS is usually a by-product.
     Mature library: `dlisio` (Equinor, LGPL), including multiple frames/runs and array curves.
   - **LAS 3.0** (multiple data sections such as tops and core) and LAS files with several runs.
   - **CSV/ASCII** importer with column and unit mapping (core and lab data).
2. **Vertical depth and references.** **[checked: no TVD, KB or surveys]**
   - Import **deviation surveys** (MD, inclination, azimuth) and compute **TVD/TVDSS** (minimum curvature).
   - **KB/GL/DF** elevations and a project datum.
   - Switch the depth axis between **MD / TVD / TVDSS**; correlating deviated wells in MD is technically wrong.
3. **Correlation with mixed depth units.** **[checked: bug, fixed]** Wells in meters and feet used the same
   pixels-per-unit. A user-selectable **display depth unit** is still missing.
4. **Undo / redo.** **[checked: missing]** Removing a track, applying a template or recomputing
   petrophysics overwrites with no way back. Standard approach: `QUndoStack` with layout, tops and curve
   changes as commands.
5. **Zone-based petrophysics and shaly-sand models.** **[checked: one global `PetroParams`]**
   - Parameters (clean/shale GR, Rw, a/m/n, ρma, cutoffs) change by formation and must be definable **per zone**.
   - Archie is only valid in clean sands: add **Simandoux / Indonesia / Waxman-Smits**.
   - **Rw** from SP or Pickett and **temperature correction** (Arps, geothermal gradient).
   - **Permeability** estimates (Timur, Coates) and **cutoff sensitivity** analysis.
6. **Trust in the results.**
   - Test with **real public data**: Volve (Equinor, open licence: LAS, DLIS, surveys, tops) and the Kansas
     Geological Survey LAS archive.
   - **Benchmark** Vsh/φ/Sw/net pay against commercial software or a reference spreadsheet.
   - Document every **equation with its reference** inside the application.
   - Real LAS files have quirks the sample set does not cover: duplicate depths, STEP=0, -999.25/-9999
     nulls, inconsistent units.
7. **Distribution and legal.**
   - **No LICENSE file [checked]**: nobody can legally reuse or redistribute the code. MIT or LGPL are both
     compatible with PySide6 (LGPL).
   - **macOS** blocks unsigned, un-notarized downloaded apps ("is damaged"); **Windows** SmartScreen warns about
     unsigned executables. Both need paid certificates.
   - Installers (MSI/DMG) and Qt licence notices in the About box.

## B. What engineers expect day to day

**Display**
- **Wrap-around (backup) scales**: when GR exceeds 150 it is drawn again on 150–300 with another style. **[checked: missing]**
- **Color-map fills** by value (GR, resistivity) besides solid and pattern fills.
- **Lithology / volume track**: stacked shale / matrix / water / hydrocarbon columns.
- **Core** (points with error bars), **interval** (perforations, DST, losses, runs) and **comment** tracks.
- **Standard log header** in the PDF and **TVD alongside MD**.

**Interaction**
- **Pick tops by clicking** in the correlation, propagating names across wells.
- **Select an interval with the mouse** for statistics, zone creation or export.
- **Graphical parameter picking**: clean/shale GR on the histogram, water line on Pickett, matrix points on
  crossplots (typed by hand today).
- **Cursor synchronized across wells**, thickness ruler, horizontal zoom.

**Curve QC and editing**
- **Depth shifting / matching** (between runs, against core), **splicing** runs, resampling.
- Despike and smoothing filters, manual interval editing, unit conversion.
- **Quality flags** (bad hole: CALI − BS, high DRHO) masking density/neutron in calculations.
- **GR normalization** across wells (needed before multi-well Vsh).

**Data management**
- Projects with **tens to hundreds of wells**: filterable well list, lazy loading, curve search.
- **User-editable mnemonic aliases** (hard-coded today).
- **Autosave and crash recovery**.
- Option to **copy data into the project** (projects reference LAS paths that can move).

**Multi-well and reporting**
- **Base map** with well coordinates and correlation sections picked on the map.
- **Multi-well crossplots and histograms** (by field or formation).
- Zone summary to **Excel (.xlsx)** and **vector** export (SVG / vector PDF) for reports.

## C. Differentiators (after A and B)
- Array curves: **borehole images** (FMI/UBI), **NMR T2** distributions, sonic waveforms.
- **Multi-mineral** model and **uncertainty** (Monte Carlo over parameters).
- **Python scripting / plugins** for user calculations.
- **Real-time (WITSML)** data for drilling follow-up.

## D. Technical robustness
- **Corpus of difficult real LAS files** in the tests and benchmarks with large files (500,000 samples,
  200 curves); current benchmarks use 2,000–9,000 samples.
- **Error logging and crash reporting** (log file, error dialog that does not close the app).
- **Unit validation in the calculator** (porosity in % vs fraction) and warnings for physically impossible
  values (φ > 0.6, Sw > 1 before clipping).

## Status

- **Phase 1 (done):** correlation unit bug fixed, LGPL-3.0-or-later license, LAS loader hardened with a
  corpus of real-world quirks. Real public datasets (Volve, KGS) still need to be added for benchmarking.
- **Phase 2 (done):** DLIS reading (one well per depth frame; array channels not yet supported),
  deviation surveys with minimum curvature, KB/DF/GL elevation, drawing in MD/TVD/TVDSS and m/ft,
  correlation in TVDSS.

- **Phase 3 (done):** curve units — recognition of file unit spellings, display conversion per curve
  or by unit system (oilfield / metric), mislabeled % and kg/m³ detected from the values, and
  calculations that convert their inputs explicitly (results no longer depend on input units).
  Undo/redo (one history per well, snapshot based, display changes excluded). Petrophysics
  parameters by zone, Simandoux and Indonesia, Rw at formation temperature (Arps, gradient on TVD or
  temperature curve), graphical picking of clean/shale GR (histogram) and Rw (Pickett plot).
  Still open from item A.5: Waxman-Smits, Rw from SP, permeability and cutoff sensitivity.

## Recommended order

| Phase | Content | Why first |
|---|---|---|
| 1 | Correlation unit bug · LICENSE · corpus of real-world LAS quirks in the tests **(done)** | Fixes a real error, makes sharing legal and gives the base to validate everything else |
| 2 | DLIS · surveys + TVD/TVDSS + datum · display depth unit **(done)** | Without these, real project data cannot be opened or correlated correctly |
| 3 | Curve units · undo/redo · zone parameters · Simandoux/Indonesia · temperature-corrected Rw · graphical parameter picking **(done)** | Interpretation becomes trustworthy and correctable |
| 4 | Wrap-around · color-map fill · lithology track · log header · click-to-pick tops | Professional presentation quality |
| 5 | Signing/notarization and installers · editable aliases · autosave · base map · multi-well | Deployment and scale |
