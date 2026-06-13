import numpy as np
import pytest

from human_microcircuit.reference_models.common.scaling import (
    scale_neuron_number,
    scale_synapse_number,
    scale_weight,
    scale_weight_sqrt,
    recurrent_input_compensation,
    recurrent_mean_input,
    adjust_weights_and_input_to_synapse_scaling,
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


def test_recurrent_input_compensation():

    input_rec = np.array([2.0, 4.0])

    dc = recurrent_input_compensation(
        input_rec=input_rec,
        tau_syn=0.5,
        K_scaling=4.0,
    )

    expected = 0.001 * 0.5 * (1.0 - np.sqrt(4.0)) * input_rec

    assert np.allclose(dc, expected)


def test_adjust_weights_and_input_to_synapse_scaling():

    PSC_ext = 100.0
    mean_matrix = np.ones((2, 2))
    DC = np.zeros(2)
    indegree = np.ones((2, 2))
    full_mean_rates = np.ones(2)

    new_PSC, new_ext, new_DC = adjust_weights_and_input_to_synapse_scaling(
        mean_PSC_matrix=mean_matrix,
        PSC_ext=PSC_ext,
        K_scaling=4.0,
        DC_amp=DC,
        bg_input_type="poisson",
        bg_rate=8.0,
        K_ext=np.ones(2),
        tau_syn=0.5,
        indegree_matrix=indegree,
        full_mean_rates=full_mean_rates,
    )

    assert new_PSC.shape == (2, 2)
    assert new_DC.shape == (2,)
    assert new_PSC[0, 0] == pytest.approx(1.0 / np.sqrt(4.0))
    assert new_ext == pytest.approx(100.0 / np.sqrt(4.0))

    input_rec = np.array(
        [
            2.0,
            2.0,
        ]
    )
    expected_rec = 0.001 * 0.5 * (1.0 - np.sqrt(4.0)) * input_rec
    expected_ext = 0.001 * 0.5 * (1.0 - np.sqrt(4.0)) * 100.0 * 1.0 * 8.0
    assert np.allclose(
        new_DC,
        expected_rec + expected_ext,
    )
