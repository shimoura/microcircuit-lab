from types import SimpleNamespace

from microcircuit_lab.analysis.areas import list_areas


def _sim(names):
    return SimpleNamespace(network=SimpleNamespace(populations={name: None for name in names}))


def test_list_areas_keeps_order_and_skips_duplicates():
    sim = _sim(["V1__L23_E", "V1__L23_I", "V2__L23_E", "V1__L4_E"])
    assert list_areas(sim) == ["V1", "V2"]


def test_list_areas_empty_for_single_area_network():
    assert list_areas(_sim(["L23_E", "L23_I"])) == []
