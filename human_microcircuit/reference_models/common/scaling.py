"""
Utilities related to scaling transformations.

This module provides generic scaling laws and transformations that
modify network or synaptic quantities while preserving specified
statistical or dynamical properties.

Typical examples include scaling of neuron numbers, synaptic weights,
or indegrees according to analytically derived relationships.
"""

from __future__ import annotations
import math
import numpy as np

from human_microcircuit.config.network import NetworkConfig
from human_microcircuit.reference_models.common.network import (
    network_mean_input,
)

def scale_neuron_number(
    value: int,
    factor: float,
) -> int:
    """
    Scale the number of neurons.
    """

    return int(round(value * factor))


def scale_synapse_number(
    value: int,
    factor: float,
) -> int:
    """
    Scale the number of synapses.
    """

    return int(round(value * factor))


def scale_weight(
    value: float,
    factor: float,
) -> float:
    """
    Scale synaptic weight.

    Potjans convention:
        J -> J / K
    """

    return value / factor


def scale_weight_sqrt(
    weight: float,
    K_scaling: float,
) -> float:
    """
    Scale synaptic weights according to Potjans & Diesmann (2014).

    Scaling preserves input fluctuations by applying

        w -> w / sqrt(K_scaling)
    """

    return weight / math.sqrt(K_scaling)


def recurrent_dc_from_network(
    mean_PSC_matrix: np.ndarray,
    indegree_matrix: np.ndarray,
    mean_rates: np.ndarray,
    tau_syn: np.ndarray,
    K_scaling: float,
) -> np.ndarray:
    """
    Compute the recurrent DC compensation from biological network
    quantities.
    """

    network_input = network_mean_input(
        mean_PSC_matrix=mean_PSC_matrix,
        indegree_matrix=indegree_matrix,
        mean_rates=mean_rates,
    )

    return network_compensation_current(
        network_input=network_input,
        tau_syn=tau_syn,
        K_scaling=K_scaling,
    )


def network_compensation_current(
    network_input: np.ndarray,
    tau_syn: float,
    K_scaling: float,
) -> np.ndarray:
    """
    Compute input compensation due to network scaling.

    Parameters
    ----------
    network_input
        Mean input to each population from the recurrent network (pA).

    tau_syn
        Synaptic time constant (ms).

    K_scaling
        Indegree scaling factor.

    Returns
    -------
    np.ndarray
        DC compensation current.
    """

    return 0.001 * tau_syn * (1.0 - np.sqrt(K_scaling)) * network_input


def external_compensation_current(
    PSC_ext: np.ndarray,
    K_ext: np.ndarray,
    bg_rate: np.ndarray,
    tau_syn: np.ndarray,
    K_scaling: float,
) -> np.ndarray:
    """
    Compute the external input compensation due to network scaling.
    """

    return 0.001 * tau_syn * (1.0 - np.sqrt(K_scaling)) * PSC_ext * K_ext * bg_rate


def scale_weights(
    network: NetworkConfig,
) -> NetworkConfig:
    """
    Apply square root synaptic weight scaling to all recurrent and external synaptic weights.
    Scaling preserves input fluctuations by applying:

    w -> w / sqrt(K_scaling)
    """

    scaling = network.scaling

    #
    # recurrent
    #
    connections = []

    for connection in network.connections:

        weight = connection.weight.model_copy(
            update={
                "mean": scale_weight_sqrt(
                    connection.weight.mean,
                    scaling.K_scaling,
                )
            }
        )

        connections.append(
            connection.model_copy(
                update={
                    "weight": weight,
                }
            )
        )

    #
    # external
    #
    inputs = {}

    for pop_name, input_cfg in network.inputs.items():

        weight = input_cfg.weight.model_copy(
            update={
                "mean": scale_weight_sqrt(
                    input_cfg.weight.mean,
                    scaling.K_scaling,
                )
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


def adjust_weights_and_input_to_synapse_scaling(
    mean_PSC_matrix,
    PSC_ext,
    K_scaling,
    DC_amp,
    bg_input_type,
    bg_rate,
    K_ext,
    tau_syn,
    indegree_matrix,
    full_mean_rates,
):
    """
    Adjust synaptic weights and input currents to compensate for synapse scaling.

    Parameters
    ----------
    PSC_ext
        External synaptic weight (pA).
    K_scaling
        Indegree scaling factor.
    mean_PSC_matrix
        Matrix of mean PSC amplitudes (pA) before scaling.
    DC_amp
        DC compensation amplitude (pA) before scaling.
    poisson_input
        Whether Poisson input is used.
    bg_rate
        External Poisson firing rate (spikes/s).
    K_ext
        External indegree for each population.
    tau_syn
        Synaptic time constant (ms).
    indegree_matrix
        Matrix of indegrees for each connection.
    full_mean_rates
        Mean firing rates of all populations (Hz).

    Returns
    -------
    tuple
        Adjusted PSC matrices and DC amplitude.
    """
    # 1. Scale recurrent PSC
    PSC_matrix_new = mean_PSC_matrix / np.sqrt(K_scaling)

    # 2. Scale external PSC
    PSC_ext_new = PSC_ext / np.sqrt(K_scaling)

    # 3. Recurrent mean input
    network_input = network_mean_input(
        mean_PSC_matrix=mean_PSC_matrix,
        indegree_matrix=indegree_matrix,
        mean_rates=full_mean_rates,
    )

    # 4. Recurrent DC compensation
    DC_amp_new = DC_amp + network_compensation_current(
        network_input=network_input,
        tau_syn=tau_syn,
        K_scaling=K_scaling,
    )

    # 5. External compensation
    if bg_input_type == "poisson":

        input_ext = PSC_ext * K_ext * bg_rate

        DC_amp_new = (
            DC_amp_new + 0.001 * tau_syn * (1.0 - np.sqrt(K_scaling)) * input_ext
        )

    return (
        PSC_matrix_new,
        PSC_ext_new,
        DC_amp_new,
    )
