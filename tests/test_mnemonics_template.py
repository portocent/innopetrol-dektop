import pytest

from innopetrol.model.mnemonics import build_triple_combo, default_scale, family_of
from innopetrol.model.template import TemplateError, apply_template, template_from_json, template_to_json
from innopetrol.model.well import Well


@pytest.mark.parametrize("mnem,fam", [("GR", "gamma_ray"), ("SGR", "gamma_ray"), ("TNPH", "neutron"),
                                      ("NPHI", "neutron"), ("LLD", "deep_res"), ("ILD", "deep_res"),
                                      ("RHOB", "density"), ("DTLN", "sonic"), ("K_3104", "permeability"),
                                      ("XYZ", None)])
def test_family_of(mnem, fam):
    assert family_of(mnem) == fam


def test_triple_combo_testdata(testdata_well):
    layout = build_triple_combo(testdata_well)
    titles = [t.title for t in layout.tracks]
    assert titles[:3] == ["Correlación", "Prof.", "Resistividad"]
    assert layout.tracks[1].is_depth
    dn = next(t for t in layout.tracks if t.title == "Densidad - Neutrón")
    assert {c.mnemonic for c in dn.curves} == {"RHOB", "TNPH"}
    assert any("gas" in f.label for f in dn.fills)
    res = next(t for t in layout.tracks if t.title == "Resistividad")
    assert all(c.log for c in res.curves)


def test_template_across_wells(samples, testdata_well):
    """Una plantilla hecha con SGR/LLD/TNPH funciona en un pozo con GR/ILD/NPHI."""
    other = Well.from_las(samples / "TotalDepthPrueba.las")
    text = template_to_json(build_triple_combo(testdata_well))
    layout, missing = apply_template(template_from_json(text), other)
    names = {c.mnemonic for t in layout.tracks for c in t.curves}
    assert {"GR", "ILD", "ILM", "RHOB"} <= names
    assert "SGR" not in names
    assert "PERMCORE" in missing
    corr = layout.tracks[0]
    assert all(f.left_curve in (None, "GR") and f.right_curve in (None, "GR") for f in corr.fills)


def test_template_rejects_garbage():
    with pytest.raises(TemplateError):
        template_from_json("{not json")
    with pytest.raises(TemplateError):
        template_from_json('{"format": "otra-cosa"}')


def test_neutron_percent_scale(samples):
    w = Well.from_las(samples / "Testdata.las")
    assert default_scale(w, "TNPH") == (0.45, -0.15, False)
    w.curves["TNPH"].values = w.curves["TNPH"].values * 100
    assert default_scale(w, "TNPH") == (45, -15, False)
