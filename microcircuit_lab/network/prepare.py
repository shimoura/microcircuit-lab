"""
Prepare a network for the simulation: the steps between the network as
written in the files and the network the simulator builds.

:func:`prepare_network` lists the steps in order. Each step is a small
function below that takes a :class:`NetworkConfig` and returns a new one;
nothing is changed in place. To add a step (e.g. a new compensation rule),
write its function here (``compensation.py`` holds the steps that add
currents) and call it from :func:`prepare_network`.
"""

from __future__ import annotations

import numpy as np

from microcircuit_lab.config.connectivity import SHARED_DISTRIBUTIONS, SHARED_RULES
from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.network.compensation import (
    compensate_lost_mean_input,
    replace_background_by_mean_current,
)
from microcircuit_lab.network.scaling import (
    scale_neuron_number,
    scale_rule_number,
    scale_weights,
)


def prepare_network(config: NetworkConfig) -> NetworkConfig:
    """
    Return the network ready to simulate; ``config`` itself is not changed.

    The steps, in order:

    1. if ``scaling`` asks for it: scale the neuron numbers (``N_scaling``),
       the indegrees (``K_scaling``) and the weights, then add the DC current
       that compensates the mean input lost by scaling (for weights in pA on
       the default receptor port: the only input whose mean current is
       known);
    2. turn each population's background rate per synapse into the rate of
       its Poisson generator (rate x indegree);
    3. with ``background_mode: mean_current``, replace the background input by a
       constant current of the same mean.

    Parameters
    ----------
    config
        The network as read from its files (see
        :func:`microcircuit_lab.network.load.read_network`).

    Returns
    -------
    NetworkConfig
        A new network description with scaled sizes, indegrees and weights,
        and the compensation currents added to ``I_e``.
    """

    network = config.model_copy(deep=True)

    if network.scaling.is_scaled:
        network = _scale_neuron_numbers(network)
        network = _scale_indegrees(network)
        network = scale_weights(network)
        network = compensate_lost_mean_input(network, original=config)

    network = _background_rate_per_neuron(network)
    network = replace_background_by_mean_current(network, original=config)

    return network


def _scale_neuron_numbers(
    network: NetworkConfig,
) -> NetworkConfig:
    """
    Apply neuron-number scaling.
    """

    scaling = network.scaling

    populations = {}

    for name, population in network.populations.items():
        scaled_size = scale_neuron_number(
            population.size,
            scaling.N_scaling,
        )
        if scaled_size < 1:
            raise ValueError(
                f"N_scaling={scaling.N_scaling} reduces population "
                f"'{name}' from {population.size} neurons to zero. "
                "Increase N_scaling to keep every configured population non-empty."
            )

        populations[name] = population.model_copy(update={"size": scaled_size})

    return network.model_copy(update={"populations": populations})


def _scale_indegrees(
    network: NetworkConfig,
) -> NetworkConfig:
    """
    Apply indegree scaling.

    Currently scales:
        - the number each connection rule takes (see scale_rule_number), for
          the whole column at once
        - background indegrees

    Synaptic weights and DC compensation are intentionally
    handled in later transformations.
    """

    scaling = network.scaling

    # Scale background indegrees
    populations = {}
    for name, population in network.populations.items():
        scaled_indegree = population.background_indegree * scaling.K_scaling
        populations[name] = population.model_copy(update={"background_indegree": scaled_indegree})

    # Scale the number each connection rule takes (n_synapses, indegree, ...),
    # for all connections at once.
    table = network.connections
    rule = table["rule"]
    _check_connections_can_scale(table, scaling.N_scaling, scaling.K_scaling)
    scaled = scale_rule_number(table["number"], rule, scaling.N_scaling, scaling.K_scaling)

    too_likely = np.flatnonzero((rule == "pairwise_bernoulli") & (scaled > 1.0))
    if too_likely.size:
        i = too_likely[0]
        raise ValueError(
            f"Connection {table['source'][i]} -> {table['target'][i]}: with N_scaling="
            f"{scaling.N_scaling} and K_scaling={scaling.K_scaling}, p={table['number'][i]} "
            f"becomes {scaled[i]:.3g}, above 1. Keeping the indegree in smaller populations "
            "needs a higher probability; increase N_scaling or lower K_scaling."
        )

    # A connection scaled to no synapse is left out.
    connections = table.with_columns(copy=False, number=scaled).keep_rows(scaled != 0)

    return network.model_copy(update={"populations": populations, "connections": connections})


def _check_connections_can_scale(table, N_scaling: float, K_scaling: float) -> None:
    """
    Raise for a connection that scaling cannot keep at the full-scale input.
    Its rule cannot keep each neuron's inputs at ``K_scaling`` times the
    full-scale number: ``one_to_one`` always gives one input, ``all_to_all``
    gives ``n_source``, which shrinks with ``N_scaling``, and a rule that is not
    shared says nothing about its scaling. Or its weights come from a project
    distribution, whose real mean, which the compensation needs, is not known
    here. (A project delay distribution is fine: scaling leaves delays alone.)
    """

    rule = table["rule"]
    reasons = (
        ((rule == "one_to_one") & (K_scaling != 1.0),
         "one_to_one gives each neuron one input at any scale, so K_scaling must be 1"),
        ((rule == "all_to_all") & (K_scaling != N_scaling),
         "all_to_all gives each neuron n_source inputs, which shrink with N_scaling, so "
         "K_scaling must equal N_scaling"),
        (~np.isin(rule, SHARED_RULES),
         "rule {rule} is not a shared one and cannot be scaled yet; scale the network in its "
         "builder, or run it at full scale"),
        (~np.isin(table["weight.distribution"], SHARED_DISTRIBUTIONS),
         "weights from a project distribution cannot be scaled yet; scale the network in its "
         "builder, or run it at full scale"),
    )
    for rows, why in reasons:
        if rows.any():
            i = int(np.flatnonzero(rows)[0])
            raise ValueError(
                f"Connection {table['source'][i]} -> {table['target'][i]} (N_scaling={N_scaling}, "
                f"K_scaling={K_scaling}): " + why.format(rule=repr(rule[i])) + "."
            )


def _background_rate_per_neuron(
    network: NetworkConfig,
) -> NetworkConfig:
    """
    Convert biological background rates into effective
    Poisson generator rates.

    The effective rate is computed as the product of the background
    rate and the background indegree, i.e.,
        effective_rate = bg_rate * K_ext
    """

    background_inputs = {}

    for pop_name, input_cfg in network.background_inputs.items():
        K_ext = network.populations[pop_name].background_indegree

        background_inputs[pop_name] = input_cfg.model_copy(update={"rate": input_cfg.rate * K_ext})

    return network.model_copy(update={"background_inputs": background_inputs})
