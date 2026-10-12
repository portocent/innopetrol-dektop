"""Quality control of the petrophysics results."""

import numpy as np
import pytest

from innopetrol.model import petro
from innopetrol.model.tops import Top
from innopetrol.model.well import Curve, Well


def well(rhob, rt, nphi=None) -> Well:
    n = len(rhob)
    curves = {
        "RHOB": Curve("RHOB", "G/C3", "", np.asarray(rhob, float)),
        "RT": Curve("RT", "OHMM", "", np.asarray(rt, float)),
    }
    if nphi is not None:
        curves["NPHI"] = Curve("NPHI", "V/V", "", np.asarray(nphi, float))
    return Well("qc", None, np.arange(1000.0, 1000.0 + n * 0.5, 0.5), "m", curves=curves)


def findings(w, **params):
    p = petro.PetroParams(rhob_curve="RHOB", rt_curve="RT", **params)
    return {(f.kind, f.zone): f for f in petro.qc_report(w, p, petro.compute(w, p))}


def test_clean_results_have_no_findings():
    w = well(np.full(100, 2.32), np.full(100, 20.0))
    assert findings(w, rw=0.05) == {}


def test_sw_above_one_and_negative_porosity():
    rhob = np.full(100, 2.32)
    rhob[:20] = 2.75  # denser than a 2.65 matrix: negative porosity
    rt = np.full(100, 20.0)
    rt[50:70] = 0.5  # below Ro = 1.25: Sw > 1 before limiting
    found = findings(well(rhob, rt), rw=0.05)
    assert found[("phi_negative", None)].count == 20 and found[("phi_negative", None)].fraction == pytest.approx(0.2)
    assert found[("sw_above_1", None)].count == 20
    assert "Rw or m" in found[("sw_above_1", None)].message()


def test_findings_per_zone_and_input_ranges():
    rhob = np.full(100, 2.32)
    rhob[80:] = 3.5  # impossible density in the lower zone
    w = well(rhob, np.full(100, 20.0), nphi=np.where(np.arange(100) < 10, 0.9, 0.2))
    w.tops = [Top("UP", 1000.0), Top("LOW", 1040.0)]  # zones only: no whole-well duplicate
    found = findings(w, nphi_curve="NPHI", phi_method="nd_average")
    assert found[("density_range", "LOW")].fraction == pytest.approx(20 / 20)
    assert ("density_range", "UP") not in found
    assert found[("neutron_range", "UP")].count == 10
    assert "zone LOW" in found[("density_range", "LOW")].message()
    assert all(zone is not None for _kind, zone in found)


def test_small_problems_are_not_reported():
    rhob = np.full(400, 2.32)
    rhob[:3] = 2.75  # 3 samples: below the minimum
    assert findings(well(rhob, np.full(400, 20.0))) == {}


def test_dialog_reports_after_computing(testdata_well, qtbot, no_modal_boxes):
    from innopetrol.model.mnemonics import build_triple_combo
    from innopetrol.ui.document import WellDocument
    from innopetrol.ui.petro_dialog import PetroDialog

    doc = WellDocument(testdata_well, build_triple_combo(testdata_well))
    d = PetroDialog(doc)
    qtbot.addWidget(d)
    d.rw.setValue(5.0)  # absurdly high Rw: Sw > 1 almost everywhere
    d._run()
    assert "SW" in doc.well.curves  # computed anyway
    assert no_modal_boxes and "Points to review" in no_modal_boxes[-1][1][2]
