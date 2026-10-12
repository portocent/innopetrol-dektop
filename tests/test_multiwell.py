"""Crossplots and histograms with several wells."""

import numpy as np
import pytest
from PySide6.QtCore import Qt

from innopetrol.model.mnemonics import build_triple_combo
from innopetrol.model.tops import Top
from innopetrol.model.well import Curve, Well
from innopetrol.ui.document import WellDocument
from innopetrol.ui.multiwell import equivalent_curve, values_as, zone_mask


@pytest.fixture
def docs(samples, qapp):
    a = Well.from_las(samples / "Testdata.las")
    b = Well.from_las(samples / "Testdata.las")
    b.name = "Other"
    # The second well calls its gamma ray GR instead of SGR and has its density in kg/m³.
    b.add_curve(Curve("GR", "GAPI", "", b.curves.pop("SGR").values))
    b.curves["RHOB"] = Curve("RHOB", "K/M3", "", b.curves["RHOB"].values * 1000)
    a.tops = [Top("A", 7800.0)]
    b.tops = [Top("A", 8000.0)]
    return [WellDocument(w, build_triple_combo(w)) for w in (a, b)]


def test_equivalent_curves_and_units(docs):
    a, b = docs
    assert equivalent_curve(b, "SGR") == "GR"
    rhob = values_as(b, "RHOB", a)  # kg/m³ converted to the g/cm³ shown in the active well
    assert np.allclose(rhob, a.well.curves["RHOB"].values, equal_nan=True)
    assert zone_mask(b, "A").sum() < zone_mask(a, "A").sum()  # each well uses its own top
    assert zone_mask(a, None).all()


def check_well(lst, doc):
    for i in range(lst.count()):
        if lst.item(i).data(Qt.UserRole) is doc:
            lst.item(i).setCheckState(Qt.Checked)


def test_crossplot_with_two_wells(docs, qtbot):
    from innopetrol.ui.crossplot import BY_WELL, CrossplotWindow

    a, b = docs
    win = CrossplotWindow(a, "nd", None, docs)
    qtbot.addWidget(win)
    n_one = win.plot.x.size
    check_well(win.wells, b)
    assert win.c.currentData() == BY_WELL  # switched to color by well
    assert win.plot.x.size == 2 * n_one and [g[0] for g in win.plot.groups] == ["Test Well 1", "Other"]
    # Density of the second well arrives in g/cm³ like the first one.
    assert np.nanmax(win.plot.y) < 4
    win.zone.setCurrentIndex(win.zone.findData("A"))
    assert win.plot.x.size == zone_mask(a, "A").sum() + zone_mask(b, "A").sum()


def test_histogram_with_two_wells(docs, qtbot):
    from innopetrol.ui.analysis import StatsDialog

    a, b = docs
    d = StatsDialog(a, "SGR", None, docs)
    qtbot.addWidget(d)
    check_well(d.wells, b)
    assert len(d.hist.series) == 2 and "Other" in d.stats.text() and "P50" in d.stats.text()
    d.show()
    qtbot.waitExposed(d)
    assert not d.hist.grab().isNull()
