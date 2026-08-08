import numpy as np

from microcircuit_lab.network.scaling import (
    scale_neuron_number,
    scale_synapse_number,
    scale_weight,
    scale_weight_sqrt,
    network_compensation_current,
    background_dc_current,
)
from microcircuit_lab.network.parameters import (
    network_mean_input,
)


def test_scale_neurons():

    assert scale_neuron_number(1000, 0.5) == 500


def test_scale_synapses():

    assert scale_synapse_number(1000, 0.5) == 500


def test_scale_weight():

    assert scale_weight(80.0, 2.0) == 40.0


def test_scale_weight_sqrt():

    assert (
        scale_weight_sqrt(
            100.0,
            4.0,
        )
        == 50.0
    )


def test_network_mean_input():

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

    result = network_mean_input(
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


def test_network_compensation_current():

    network_input = np.array([2.0, 4.0])

    dc = network_compensation_current(
        network_input=network_input,
        tau_syn=0.5,
        K_scaling=4.0,
    )

    expected = 0.001 * 0.5 * (1.0 - np.sqrt(4.0)) * network_input

    assert np.allclose(dc, expected)


def test_background_dc_current():

    PSC_ext = np.array([50.0, 60.0])
    K_ext = np.array([1000.0, 1500.0])
    bg_rate = np.array([8.0, 8.0])
    tau_syn = np.array([0.5, 0.5])

    dc = background_dc_current(
        PSC_ext=PSC_ext,
        K_ext=K_ext,
        bg_rate=bg_rate,
        tau_syn=tau_syn,
    )

    expected = 0.001 * tau_syn * PSC_ext * K_ext * bg_rate

    assert np.allclose(dc, expected)


