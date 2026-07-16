import numpy as np
import pytest

from microcircuit_lab.io.config import NetworkConfigLoader
from microcircuit_lab.network.preprocessing import (
    NetworkPreprocessor,
)
from microcircuit_lab.network.parameters import (
    full_num_neurons,
    full_num_synapses,
    indegree_matrix,
    full_mean_rates,
    external_indegrees,
    external_weights,
)
from microcircuit_lab.io.files import read_network_directory


def test_reference_matrices():

    network_files = read_network_directory("configs/network/pd14")

    network = NetworkConfigLoader(network_files).build()

    neurons = full_num_neurons(network)
    synapses = full_num_synapses(network)
    indegrees = indegree_matrix(network)

    assert neurons.ndim == 1
    assert synapses.ndim == 2
    assert indegrees.ndim == 2

    assert synapses.shape == (8, 8)
    assert indegrees.shape == (8, 8)

    assert np.all(neurons > 0.0)

    assert neurons[0] == 20683
    assert neurons[1] == 5834
    assert synapses[0, 0] > 0.0
    assert indegrees[0, 0] == pytest.approx(synapses[0, 0] / neurons[0])


def test_preprocessing_preserves_original_network():

    network_files = read_network_directory("configs/network/pd14")

    original = NetworkConfigLoader(network_files).build()

    original = original.model_copy(
        update={
            "scaling": original.scaling.model_copy(
                update={
                    "N_scaling": 0.2,
                    "K_scaling": 0.2,
                }
            )
        }
    )

    derived = NetworkPreprocessor(original).process()

    #
    # original untouched
    #
    assert original.populations["L23_E"].size == 20683

    #
    # derived scaled
    #
    assert derived.populations["L23_E"].size == round(20683 * 0.2)

    #
    # they are different objects
    #
    assert original is not derived
    assert original.populations["L23_E"].background_indegree == 1600
    assert derived.populations["L23_E"].background_indegree == pytest.approx(1600 * 0.2)
    assert original.populations["L23_E"] is not derived.populations["L23_E"]


def test_full_mean_rates():

    network_files = read_network_directory("configs/network/pd14")

    network = NetworkConfigLoader(network_files).build()

    rates = full_mean_rates(network)

    assert rates.shape == (8,)

    assert rates[0] == pytest.approx(0.903)
    assert rates[1] == pytest.approx(2.965)
    assert rates[2] == pytest.approx(4.414)
    assert rates[3] == pytest.approx(5.876)
    assert rates[4] == pytest.approx(7.569)
    assert rates[5] == pytest.approx(8.633)
    assert rates[6] == pytest.approx(1.105)
    assert rates[7] == pytest.approx(7.829)


def test_external_indegrees():

    network_files = read_network_directory("configs/network/pd14")

    network = NetworkConfigLoader(network_files).build()

    K_ext = external_indegrees(network)

    assert K_ext.shape == (8,)

    assert K_ext[0] == 1600
    assert K_ext[1] == 1500
    assert K_ext[2] == 2100
    assert K_ext[3] == 1900
    assert K_ext[4] == 2000
    assert K_ext[5] == 1900
    assert K_ext[6] == 2900
    assert K_ext[7] == 2100


def test_external_weights():

    network_files = read_network_directory("configs/network/pd14")

    network = NetworkConfigLoader(network_files).build()

    weights = external_weights(network)

    assert weights.shape == (8,)

    #
    # Before PSP->PSC conversion these are biological PSP amplitudes.
    #
    assert np.allclose(
        weights,
        0.15,
    )
