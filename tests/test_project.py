import numpy as np

from innopetrol.model import petro
from innopetrol.model.mnemonics import build_triple_combo
from innopetrol.model.project import WellEntry, load_project, save_project
from innopetrol.model.tops import Top


def test_project_roundtrip(testdata_well, tmp_path):
    w = testdata_well
    w.tops = [Top("A", 7700, "#ff0000")]
    params = petro.PetroParams(gr_curve="SGR", rhob_curve="RHOB", rt_curve="LLD")
    for c in petro.compute(w, params):
        w.add_curve(c)
    layout = build_triple_combo(w)
    save_project(tmp_path / "p.ipproj", [WellEntry(w, layout, params)])

    res = load_project(tmp_path / "p.ipproj")
    assert not res.errors
    e = res.entries[0]
    assert e.well.tops[0].name == "A"
    assert np.allclose(e.well.curves["SW"].values, w.curves["SW"].values, equal_nan=True)
    assert e.layout == layout
    assert e.petro == params
