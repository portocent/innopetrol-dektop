"""Result tracks of the petrophysics and where they are placed."""

from innopetrol.model import petro
from innopetrol.model.layout import LogLayout, TrackSpec
from innopetrol.model.mnemonics import build_triple_combo
from innopetrol.model.petro_layout import place_tracks, results_tracks


def computed_well(testdata_well):
    params = petro.PetroParams(gr_curve="SGR", rhob_curve="RHOB", rt_curve="LLD")
    curves = petro.compute(testdata_well, params)
    for c in curves:
        testdata_well.add_curve(c)
    return testdata_well, [c.mnemonic for c in curves]


def test_results_tracks(testdata_well):
    well, names = computed_well(testdata_well)
    tracks = results_tracks(well, names)
    assert [t.kind for t in tracks] == ["curves", "curves", "volumes"]
    assert [c.mnemonic for c in tracks[0].curves] == ["VSH", "PHIE", "SW"]
    assert [c.mnemonic for c in tracks[1].curves] == ["RES_FLAG", "PAY_FLAG"]
    assert results_tracks(well, ["VSH"])[0].curves[0].mnemonic == "VSH"
    assert results_tracks(well, []) == [t for t in results_tracks(well, []) if t.is_volumes]


def test_place_after_density_neutron_then_replace(testdata_well):
    well, names = computed_well(testdata_well)
    layout = build_triple_combo(well)
    layout.tracks = [t for t in layout.tracks if not any(c.mnemonic in names for c in t.curves)]
    density = next(i for i, t in enumerate(layout.tracks) if any(c.family == "density" for c in t.curves))
    n = len(layout.tracks)
    place_tracks(layout, results_tracks(well, names))
    assert len(layout.tracks) == n + 3
    assert [t.kind for t in layout.tracks[density + 1 : density + 4]] == ["curves", "curves", "volumes"]
    place_tracks(layout, results_tracks(well, names))  # computing again replaces, never duplicates
    assert len(layout.tracks) == n + 3


def test_place_at_the_end_without_reference_tracks(testdata_well):
    well, names = computed_well(testdata_well)
    layout = LogLayout([TrackSpec(title="only")])
    place_tracks(layout, results_tracks(well, names))
    assert layout.tracks[0].title == "only" and len(layout.tracks) == 4
