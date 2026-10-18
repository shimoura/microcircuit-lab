"""Population names → area, layer and cell type, for colours and plot layout."""

import pytest

from microcircuit_lab.analysis.plot_styles import population_metadata


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("L23_E", (None, "L23", "E")),
        ("L4_I", (None, "L4", "I")),
        ("V1__L5_E", ("V1", "L5", "E")),
        ("A__L23_PV", ("A", "L23", "PV")),
        ("B__L6_SOM", ("B", "L6", "SOM")),
        ("B__L5_VIP", ("B", "L5", "VIP")),
        ("E", (None, None, "E")),
        ("I", (None, None, "I")),
        ("thalamus", (None, None, None)),
    ],
)
def test_population_metadata(name, expected):
    assert population_metadata(name) == expected
