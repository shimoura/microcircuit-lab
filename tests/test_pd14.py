import numpy as np

from human_microcircuit.physiology.pd14 import (
    num_synapses_from_conn_prob,
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