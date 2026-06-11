import math

import numpy as np
import pytest

from human_microcircuit.builders.parameter_builder import (
    ParameterBuilder,
)
from human_microcircuit.builders.config_builder import ConfigBuilder
from human_microcircuit.physiology.pd14 import (
    num_synapses_from_conn_prob,
    dc_input_compensating_poisson,
    adjust_weights_and_input_to_synapse_scaling,
    recurrent_dc_compensation,
    recurrent_mean_input,
)
from human_microcircuit.physiology.synaptic_parameters import psp_to_psc
from human_microcircuit.utils.io import read_network_directory


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

    expected = 8.0 * 1600 * 0.5 * 87.8 * 1e-3

    assert dc == pytest.approx(expected)


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
    assert new_PSC[0, 0] == pytest.approx(1.0 / np.sqrt(4.0))
    assert new_ext == pytest.approx(100.0 / np.sqrt(4.0))


def test_pd14_parameter_builder():

    network_files = read_network_directory("configs/network/pd14")

    network = ParameterBuilder(ConfigBuilder(network_files).build()).build()

    assert network.populations["L23_E"].size == round(20683 * 0.2)

    assert network.populations["L23_I"].size == round(5834 * 0.2)

    assert network.inputs["L23_E"].rate == pytest.approx(8.0 * 1600 * 0.2)

    assert network.inputs["L23_E"].rate == 8.0 * 1600 * 0.2

    assert network.populations["L23_E"].background_indegree == pytest.approx(1600 * 0.2)


def test_pd14_first_weight():

    network_files = read_network_directory("configs/network/pd14")

    network = ParameterBuilder(ConfigBuilder(network_files).build()).build()

    expected = psp_to_psc(
        psp=0.15,
        C_m=250.0,
        tau_m=10.0,
        tau_syn=0.5,
    ) / math.sqrt(0.2)

    assert network.connections[0].weight.mean == pytest.approx(expected)


def test_recurrent_mean_input():

    PSC = np.array(
        [
            [2.0, 2.0],
            [3.0, 3.0],
        ]
    )

    indegree = np.array(
        [
            [10.0, 20.0],
            [30.0, 40.0],
        ]
    )

    rates = np.array(
        [
            5.0,
            7.0,
        ]
    )

    result = recurrent_mean_input(
        mean_PSC_matrix=PSC,
        indegree_matrix=indegree,
        mean_rates=rates,
    )

    expected = np.array(
        [
            2 * 10 * 5 + 2 * 20 * 7,
            3 * 30 * 5 + 3 * 40 * 7,
        ]
    )

    assert np.allclose(result, expected)


def test_recurrent_dc_compensation():

    input_rec = np.array(
        [
            1000.0,
            2000.0,
        ]
    )

    result = recurrent_dc_compensation(
        input_rec=input_rec,
        tau_syn=0.5,
        K_scaling=4.0,
    )

    expected = 0.001 * 0.5 * (1.0 - np.sqrt(4.0)) * input_rec

    assert np.allclose(result, expected)
