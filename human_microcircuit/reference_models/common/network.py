"""
Utilities operating on complete network descriptions.

This module provides functions that derive matrices or vectors from a
NetworkConfig representation without modifying its underlying biological
meaning. These quantities are commonly used by builders and analytical
routines.

Typical examples include indegree matrices, external indegree vectors,
mean synaptic weight matrices, and other derived network-level
representations.
"""

from __future__ import annotations

import numpy as np

from human_microcircuit.config.network import NetworkConfig
from human_microcircuit.reference_models.common.synapses import (
    psp_to_psc_iaf_psc_exp,
)


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


def full_mean_rates(network: NetworkConfig) -> np.ndarray:
    """
    Return the full mean firing rates as a vector.
    """

    if network.reference is None:
        raise ValueError(
            "NetworkConfig.reference is required to obtain " "reference firing rates."
        )

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


def external_psc_weights(
    network: NetworkConfig,
) -> np.ndarray:
    """
    Return the external weights converted from
    biological PSP amplitudes to PSC amplitudes.
    """

    return np.asarray(
        [
            psp_to_psc_iaf_psc_exp(
                psp=network.inputs[name].weight.mean,
                C_m=network.populations[name].neuron.parameters.C_m,
                tau_m=network.populations[name].neuron.parameters.tau_m,
                tau_syn=network.populations[name].neuron.parameters.tau_syn_ex,
            )
            for name in network.populations
        ],
        dtype=float,
    )


def mean_psc_matrix(
    network: NetworkConfig,
) -> np.ndarray:
    """
    Return the biological mean PSC matrix.
    """

    from human_microcircuit.reference_models.common.synapses import (
        psp_to_psc_iaf_psc_exp,
    )

    pop_names = list(network.populations.keys())
    name_to_index = {name: i for i, name in enumerate(pop_names)}

    n = len(pop_names)

    matrix = np.zeros((n, n), dtype=float)

    for connection in network.connections:

        i = name_to_index[connection.target]
        j = name_to_index[connection.source]

        target = network.populations[connection.target]

        if connection.weight.mean >= 0:
            tau_syn = target.neuron.parameters.tau_syn_ex
        else:
            tau_syn = target.neuron.parameters.tau_syn_in

        matrix[i, j] = psp_to_psc_iaf_psc_exp(
            psp=connection.weight.mean,
            C_m=target.neuron.parameters.C_m,
            tau_m=target.neuron.parameters.tau_m,
            tau_syn=tau_syn,
        )

    return matrix


def tau_syn_ex(
    network: NetworkConfig,
) -> np.ndarray:
    """
    Return the excitatory synaptic time constant for each population.
    """

    return np.asarray(
        [
            network.populations[name].neuron.parameters.tau_syn_ex
            for name in network.populations
        ],
        dtype=float,
    )


def convert_network_psp_to_psc(
    network: NetworkConfig,
) -> NetworkConfig:
    """
    Convert all synaptic weights stored as PSP amplitudes into
    PSC amplitudes.

    The conversion is performed independently for each target
    population using its neuron parameters.

    Currently this transformation is only implemented for
    current-based leaky integrate-and-fire neurons with
    exponential synaptic currents (`iaf_psc_exp`).
    """

    connections = []
    for connection in network.connections:

        target = network.populations[connection.target]
        if target.neuron.model != "iaf_psc_exp":
            raise NotImplementedError(...)

        if connection.weight.mean >= 0:
            tau_syn = target.neuron.parameters.tau_syn_ex
        else:
            tau_syn = target.neuron.parameters.tau_syn_in

        weight = connection.weight.model_copy(
            update={
                "mean": psp_to_psc_iaf_psc_exp(
                    psp=connection.weight.mean,
                    C_m=target.neuron.parameters.C_m,
                    tau_m=target.neuron.parameters.tau_m,
                    tau_syn=tau_syn,
                ),
                "unit": "PSC",
            }
        )

        connections.append(
            connection.model_copy(
                update={
                    "weight": weight,
                }
            )
        )

    inputs = {}
    for pop_name, input_cfg in network.inputs.items():

        target = network.populations[pop_name]
        tau_syn = target.neuron.parameters.tau_syn_ex

        weight = input_cfg.weight.model_copy(
            update={
                "mean": psp_to_psc_iaf_psc_exp(
                    psp=input_cfg.weight.mean,
                    C_m=target.neuron.parameters.C_m,
                    tau_m=target.neuron.parameters.tau_m,
                    tau_syn=tau_syn,
                ),
                "unit": "PSC",
            }
        )

        inputs[pop_name] = input_cfg.model_copy(
            update={
                "weight": weight,
            }
        )

    return network.model_copy(
        update={
            "connections": connections,
            "inputs": inputs,
        }
    )


def network_mean_input(
    mean_PSC_matrix: np.ndarray,
    indegree_matrix: np.ndarray,
    mean_rates: np.ndarray,
) -> np.ndarray:
    """
    Compute the mean recurrent synaptic input used for DC compensation
    when scaling synaptic weights.

    Parameters
    ----------
    mean_PSC_matrix
        Matrix of mean PSC amplitudes (pA).

    indegree_matrix
        Matrix of indegrees.

    mean_rates
        Mean firing rate of each source population (Hz).

    Returns
    -------
    np.ndarray
        Mean recurrent input for each target population.
    """

    return np.sum(
        mean_PSC_matrix * indegree_matrix * mean_rates,
        axis=1,
    )
