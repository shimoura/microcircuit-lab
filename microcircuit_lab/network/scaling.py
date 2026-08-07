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

from microcircuit_lab.config.network import NetworkConfig

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
    Scale synaptic weight linearly: preserves mean input, not variance.

        J -> J / K

    NOT currently wired to ScalingConfig.preserve_mean_input /
    preserve_variance -- scale_weights() always uses scale_weight_sqrt
    regardless of those flags. See scale_weight_sqrt's docstring.
    """

    return value / factor


def scale_weight_sqrt(
    weight: float,
    K_scaling: float,
) -> float:
    """
    Scale synaptic weights according to Potjans & Diesmann (2014).

    Scaling preserves input fluctuations (variance), not mean input,
    by applying

        w -> w / sqrt(K_scaling)

    scale_weights() always applies this, regardless of
    ScalingConfig.preserve_mean_input/preserve_variance -- those flags
    are currently declarative only (see ScalingConfig's docstring note).
    compensate_recurrent_input's DC injection is what actually restores
    the mean input this rule doesn't preserve on its own.
    """

    return weight / math.sqrt(K_scaling)


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


def background_compensation_current(
    PSC_ext: np.ndarray,
    K_ext: np.ndarray,
    bg_rate: np.ndarray,
    tau_syn: np.ndarray,
    K_scaling: float,
) -> np.ndarray:
    """
    Compute the background input compensation due to network scaling.
    """

    return 0.001 * tau_syn * (1.0 - np.sqrt(K_scaling)) * PSC_ext * K_ext * bg_rate


def scale_weights(
    network: NetworkConfig,
) -> NetworkConfig:
    """
    Scale all recurrent and external synaptic weights for K_scaling.

    ``scaling.preserve_variance`` selects which law is applied:

    - True (default): w -> w / sqrt(K_scaling) (scale_weight_sqrt).
      Preserves input fluctuations; biases mean input, which
      NetworkPreprocessor._apply_scaling_compensation corrects for via DC
      current injection when scaling.preserve_mean_input is also True.
    - False: w -> w / K_scaling (scale_weight). Preserves mean input
      directly (indegree * weight is invariant under this law), at the
      cost of fluctuations -- no compensation is applied or needed for
      the mean in this case.
    """

    scaling = network.scaling
    weight_scaler = scale_weight_sqrt if scaling.preserve_variance else scale_weight

    #
    # recurrent
    #
    connections = []

    for connection in network.connections:

        weight = connection.weight.model_copy(
            update={
                "mean": weight_scaler(
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
    # background
    #
    background_inputs = {}

    for pop_name, input_cfg in network.background_inputs.items():

        weight = input_cfg.weight.model_copy(
            update={
                "mean": weight_scaler(
                    input_cfg.weight.mean,
                    scaling.K_scaling,
                )
            }
        )

        background_inputs[pop_name] = input_cfg.model_copy(
            update={
                "weight": weight,
            }
        )

    return network.model_copy(
        update={
            "connections": connections,
            "background_inputs": background_inputs,
        }
    )
