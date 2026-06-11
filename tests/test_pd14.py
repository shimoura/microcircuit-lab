import numpy as np

from human_microcircuit.physiology.pd14 import (
    num_synapses_from_conn_prob,
    dc_input_compensating_poisson,
    adjust_weights_and_input_to_synapse_scaling,
)


def test_zero_connection_probability():

    assert (
        num_synapses_from_conn_prob(
            conn_prob=0.0,
            n_source=100,
            n_target=200,
        )
        == 0
    )


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


def test_adjust_weights_shape():

    PSC = np.ones((2, 2))

    PSC_ext = 100.0

    mean_matrix = np.ones((2, 2))

    mean_ext = np.ones(2)

    DC = np.zeros(2)

    new_PSC, new_ext, new_DC = adjust_weights_and_input_to_synapse_scaling(
        PSC_matrix_mean=PSC,
        PSC_ext=PSC_ext,
        K_scaling=4.0,
        mean_PSC_matrix=mean_matrix,
        mean_PSC_ext=mean_ext,
        DC_amp=DC,
        poisson_input=True,
        bg_rate=8.0,
        K_ext=np.ones(2),
        tau_syn=0.5,
    )

    assert new_PSC.shape == (2, 2)

    assert new_DC.shape == (2,)
