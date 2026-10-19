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


def scale_rule_number(
    value: int | float,
    rule: str,
    N_scaling: float,
    K_scaling: float,
) -> int | float:
    """
    Scale the number a connection rule takes (see ``ConnectionConfig``) so
    that every neuron keeps ``K_scaling`` times its synapses.

    The total number of synapses scales with ``N_scaling * K_scaling``, the
    indegree and outdegree with ``K_scaling``, and the connection
    probability with ``K_scaling / N_scaling``, since both populations
    shrink by ``N_scaling``.
    """

    if rule == "pairwise_bernoulli":
        return value * K_scaling / N_scaling
    if rule == "fixed_total_number":
        return scale_synapse_number(value, N_scaling * K_scaling)
    return scale_synapse_number(value, K_scaling)


def scale_weight(
    value: float,
    factor: float,
) -> float:
    """
    Scale synaptic weight linearly: preserves mean input, not variance.

        J -> J / K

    Used by scale_weights() when ScalingConfig.preserve_variance is
    False. No DC compensation is needed (or applied) in that case,
    since this law introduces no mean-input bias to correct for. See
    scale_weight_sqrt's docstring for the alternative (default) law.
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

    Used by scale_weights() when ScalingConfig.preserve_variance is
    True (the default). prepare_network (step _compensate_lost_mean_input)
    is what actually restores the mean input this rule doesn't preserve
    on its own, via DC current injection, when preserve_mean_input is
    also True.
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


def background_dc_current(
    PSC_ext: np.ndarray,
    K_ext: np.ndarray,
    bg_rate: np.ndarray,
    tau_syn: np.ndarray,
) -> np.ndarray:
    """
    Compute the constant current equivalent to the mean of a full-strength
    background Poisson drive (bg_rate spikes/s onto K_ext synapses of
    amplitude PSC_ext, pA, with synaptic time constant tau_syn, ms).

    Used to replace the background Poisson generator entirely with DC
    input, per Potjans & Diesmann (2014)'s comparison of the two drive
    types (their Fig. 5) -- see
    prepare_network (step _replace_background_by_dc). Always computed
    from the original (unscaled) network, independent of K_scaling,
    since the target mean is the full biological background input
    regardless of any N/K scaling applied to the recurrent network.
    """

    return 0.001 * tau_syn * PSC_ext * K_ext * bg_rate


def scale_weights(
    network: NetworkConfig,
) -> NetworkConfig:
    """
    Scale all recurrent and external synaptic weights for K_scaling.

    ``scaling.preserve_variance`` selects which law is applied:

    - True (default): w -> w / sqrt(K_scaling) (scale_weight_sqrt).
      Preserves input fluctuations; biases mean input, which
      prepare_network (step _compensate_lost_mean_input) corrects for via DC
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
