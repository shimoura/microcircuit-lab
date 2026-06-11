import numpy as np
import pytest

from human_microcircuit.builders.config_builder import ConfigBuilder
from human_microcircuit.builders.parameter_builder import (
    ParameterBuilder,
)
from human_microcircuit.physiology.reference import (
    full_num_neurons,
    full_num_synapses,
    indegree_matrix,
)
from human_microcircuit.utils.io import read_network_directory


def test_reference_matrices():

    network_files = read_network_directory("configs/network/pd14")

    network = ParameterBuilder(ConfigBuilder(network_files).build()).build()

    neurons = full_num_neurons(network)
    synapses = full_num_synapses(network)
    indegrees = indegree_matrix(network)

    assert neurons.ndim == 1
    assert synapses.ndim == 2
    assert indegrees.ndim == 2

    assert synapses.shape == (8, 8)
    assert indegrees.shape == (8, 8)

    assert np.all(neurons > 0.0)

    assert neurons[0] == pytest.approx(20683, abs=2)
    assert neurons[1] == pytest.approx(5834, abs=2)
    assert synapses[0, 0] > 0.0
    assert indegrees[0, 0] == pytest.approx(synapses[0, 0] / neurons[0])
