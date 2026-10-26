import numpy as np
import pytest

from microcircuit_lab.builder_tools import scale_network
from microcircuit_lab.config.reference import ReferenceConfig
from microcircuit_lab.network.load import assemble_network, read_network_files
from microcircuit_lab.network.mean_input import (
    background_indegrees,
    background_weights,
    full_mean_rates,
    full_num_neurons,
    full_num_synapses,
    indegree_matrix,
)


def test_reference_matrices():

    network_files = read_network_files("configs/network/toy")

    network = assemble_network(network_files)

    neurons = full_num_neurons(network)
    synapses = full_num_synapses(network)
    indegrees = indegree_matrix(network)

    n_pop = len(network.populations)

    assert neurons.ndim == 1
    assert synapses.ndim == 2
    assert indegrees.ndim == 2

    assert synapses.shape == (n_pop, n_pop)
    assert indegrees.shape == (n_pop, n_pop)

    assert np.all(neurons > 0.0)

    expected_sizes = [pop.size for pop in network.populations.values()]
    assert list(neurons) == expected_sizes
    assert synapses[0, 0] > 0.0
    assert indegrees[0, 0] == pytest.approx(synapses[0, 0] / neurons[0])


def test_scale_network_keeps_the_original_network():
    original = assemble_network(read_network_files("configs/network/toy"))
    original_size = original.populations["E"].size
    original_indegree = original.populations["E"].background_indegree

    # Only the N/K arithmetic: no compensation.
    derived = scale_network(
        original, N_scaling=0.2, K_scaling=0.2, scaled_from="toy", preserve_mean_input=False
    )

    assert original.populations["E"].size == original_size
    assert original.populations["E"].background_indegree == original_indegree
    assert derived.populations["E"].size == round(original_size * 0.2)
    assert derived.populations["E"].background_indegree == pytest.approx(original_indegree * 0.2)
    assert original is not derived and original.populations["E"] is not derived.populations["E"]


def test_full_mean_rates():

    network_files = read_network_files("configs/network/toy")

    network = assemble_network(network_files)

    #
    # toy's own reference.yaml has no published rates -- set some
    # directly here, since this test is only about full_mean_rates()
    # correctly reading whatever reference.full_mean_rates holds.
    #
    rates_by_population = {"E": 5.5, "I": 12.3}
    network = network.model_copy(
        update={"reference": ReferenceConfig(full_mean_rates=rates_by_population)}
    )

    rates = full_mean_rates(network)

    assert rates.shape == (len(network.populations),)
    assert list(rates) == [rates_by_population[name] for name in network.populations]


def test_background_indegrees():

    network_files = read_network_files("configs/network/toy")

    network = assemble_network(network_files)

    K_ext = background_indegrees(network)

    assert K_ext.shape == (len(network.populations),)
    expected = [pop.background_indegree for pop in network.populations.values()]
    assert list(K_ext) == expected


def test_background_weights():

    network_files = read_network_files("configs/network/toy")

    network = assemble_network(network_files)

    weights = background_weights(network)

    assert weights.shape == (len(network.populations),)

    expected = [network.background_inputs[name].weight.mean for name in network.populations]
    assert np.allclose(weights, expected)
