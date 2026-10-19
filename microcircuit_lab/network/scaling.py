"""
Formulas for scaling the number of neurons, synapses and weights, and for the
constant currents that make up for the mean input scaling removes.
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
    that every neuron has ``K_scaling`` times as many synapses.

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
    Scale a weight linearly, ``J -> J / K``. This keeps the mean input but not
    its variance.

    ``scale_weights`` uses it when ``preserve_variance`` is false. No
    compensation current is needed then, because the mean does not change.
    """

    return value / factor


def scale_weight_sqrt(
    weight: float,
    K_scaling: float,
) -> float:
    """
    Scale synaptic weights as in van Albada, Helias & Diesmann (2015), PLoS
    Comput Biol 11:e1004490 (also used by Potjans & Diesmann 2014's code).

    This keeps the fluctuations of the input (its variance) but not its mean::

        w -> w / sqrt(K_scaling)

    ``scale_weights`` uses it when ``preserve_variance`` is true (the default).
    The step ``compensate_lost_mean_input`` then restores the mean with a
    constant current, if ``preserve_mean_input`` is also true.
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
    Constant current (pA) with the same mean as the background Poisson input:
    ``bg_rate`` (spikes/s) onto ``K_ext`` synapses of amplitude ``PSC_ext`` (pA),
    with synaptic time constant ``tau_syn`` (ms).

    The step ``replace_background_by_mean_current`` uses it. It is computed for
    the original, unscaled network, so ``K_scaling`` does not change it.
    """

    return 0.001 * tau_syn * PSC_ext * K_ext * bg_rate


def scale_weights(
    network: NetworkConfig,
) -> NetworkConfig:
    """
    Scale the weights of all recurrent connections and background inputs for
    ``K_scaling``.

    ``scaling.preserve_variance`` selects the law:

    - True (default): ``w / sqrt(K_scaling)`` (``scale_weight_sqrt``). This keeps
      the fluctuations of the input but changes its mean. The step
      ``compensate_lost_mean_input`` restores the mean with a constant current
      if ``scaling.preserve_mean_input`` is also true.
    - False: ``w / K_scaling`` (``scale_weight``). This keeps the mean input
      (indegree times weight does not change) but not the fluctuations, and
      needs no compensation.
    """

    scaling = network.scaling
    weight_scaler = scale_weight_sqrt if scaling.preserve_variance else scale_weight

    # Recurrent connections.
    connections = []

    for connection in network.connections:
        mean = weight_scaler(connection.weight.mean, scaling.K_scaling)
        weight = connection.weight.model_copy(update={"mean": mean})
        connections.append(connection.model_copy(update={"weight": weight}))

    # Background inputs.
    background_inputs = {}

    for pop_name, input_cfg in network.background_inputs.items():
        mean = weight_scaler(input_cfg.weight.mean, scaling.K_scaling)
        weight = input_cfg.weight.model_copy(update={"mean": mean})
        background_inputs[pop_name] = input_cfg.model_copy(update={"weight": weight})

    return network.model_copy(
        update={"connections": connections, "background_inputs": background_inputs}
    )
