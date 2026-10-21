"""
Formulas for scaling the number of neurons, synapses and weights. The constant
currents that make up for the mean input scaling removes are in
``compensation.py``.
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


def scale_rule_number(value, rule, N_scaling: float, K_scaling: float):
    """
    Scale the number a connection rule takes (see ``ConnectionConfig``) so
    that every neuron has ``K_scaling`` times as many synapses:

    ==================== ======================== ===========================
    rule                 number                   scaled by
    ==================== ======================== ===========================
    fixed_total_number   n_synapses               N_scaling x K_scaling
    fixed_indegree       indegree                 K_scaling
    fixed_outdegree      outdegree                K_scaling
    pairwise_bernoulli   p                        K_scaling / N_scaling
    ==================== ======================== ===========================

    The probability grows by 1 / N_scaling because both populations shrink by
    N_scaling. Numbers of synapses are rounded to whole numbers. ``value``
    and ``rule`` may be a single value or one value per connection.
    """

    value, rule = np.asarray(value, dtype=float), np.asarray(rule)
    count_factor = np.where(rule == "fixed_total_number", N_scaling * K_scaling, K_scaling)
    return np.where(
        rule == "pairwise_bernoulli",
        value * K_scaling / N_scaling,
        np.round(value * count_factor),
    )


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

    # Recurrent connections: the whole weight column at once.
    connections = network.connections.with_columns(copy=False, **{
        "weight.mean": weight_scaler(network.connections["weight.mean"], scaling.K_scaling)
    })

    # Background inputs.
    background_inputs = {}

    for pop_name, input_cfg in network.background_inputs.items():
        mean = weight_scaler(input_cfg.weight.mean, scaling.K_scaling)
        weight = input_cfg.weight.model_copy(update={"mean": mean})
        background_inputs[pop_name] = input_cfg.model_copy(update={"weight": weight})

    return network.model_copy(
        update={"connections": connections, "background_inputs": background_inputs}
    )
