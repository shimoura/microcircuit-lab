"""
Utilities for constructing reference matrices from the network
configuration.
"""

from __future__ import annotations

import numpy as np

from human_microcircuit.config.network import NetworkConfig


def full_num_neurons(network: NetworkConfig) -> np.ndarray:
    """
    Return the full neuron numbers as a vector.

    These correspond to the biological (unscaled) network.
    """

    return np.asarray(
        [pop.size for pop in network.populations.values()],
        dtype=float,
    )


def full_num_synapses(network: NetworkConfig) -> np.ndarray:
    """
    Return the full synapse numbers as a matrix.

    These correspond to the biological (unscaled) network.
    """

    pop_names = list(network.populations.keys())
    n = len(pop_names)

    matrix = np.zeros((n, n), dtype=float)

    name_to_index = {name: i for i, name in enumerate(pop_names)}

    for connection in network.connections:

        i = name_to_index[connection.target]
        j = name_to_index[connection.source]

        matrix[i, j] = connection.n_synapses

    return matrix


def indegree_matrix(network: NetworkConfig) -> np.ndarray:
    """
    Return the biological indegree matrix.
    """

    neurons = full_num_neurons(network)
    synapses = full_num_synapses(network)

    return synapses / neurons[:, np.newaxis]


def full_mean_rates(
    network: NetworkConfig,
) -> np.ndarray:
    """
    Return the reference firing rates in
    population order.
    """

    return np.asarray(
        [network.reference.full_mean_rates[name] for name in network.populations],
        dtype=float,
    )


def external_indegrees(network: NetworkConfig) -> np.ndarray:
    return np.asarray(
        [pop.background_indegree for pop in network.populations.values()],
        dtype=float,
    )


def external_weights(network: NetworkConfig) -> np.ndarray:
    return np.asarray(
        [network.inputs[name].weight.mean for name in network.populations],
        dtype=float,
    )
