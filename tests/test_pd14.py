import numpy as np

from human_microcircuit.physiology.pd14 import (
    num_synapses_from_conn_prob,
    dc_input_compensating_poisson,
)


def test_zero_connection_probability():

    assert num_synapses_from_conn_prob(
        conn_prob=0.0,
        n_source=100,
        n_target=200,
    ) == 0


def test_positive_connection_probability():

    n = num_synapses_from_conn_prob(
        conn_prob=0.1,
        n_source=1000,
        n_target=500,
    )

    assert n > 0

def test_dc_input_compensation():

    dc = dc_input_compensating_poisson(
        bg_rate=8.0,
        K_ext=1600,
        tau_syn=0.5,
        PSC_ext=87.8,
    )

    assert dc > 0.0