import pytest

from human_microcircuit.physiology.dc_compensation import (
    dc_input_compensation,
)


def test_dc_input_compensation():

    current = dc_input_compensation(
        delta_weight=10.0,
        rate=8.0,
        indegree=1000.0,
        tau_syn=0.5,
    )

    assert current == pytest.approx(40.0)