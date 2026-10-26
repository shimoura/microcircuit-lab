"""
Scale a network down: fewer neurons, fewer synapses per neuron, stronger
weights, and a constant current for the mean input that is lost.

:func:`scale_network` returns the scaled network, with every scaled number in
it and a record of how it was scaled; nothing is scaled when the network runs.
Builders, scripts and sweeps call it; a project that wants other rules copies
it, changes it and calls its own copy. The formulas are the functions below;
the constant currents are in ``constant_current.py``.
"""

from __future__ import annotations

import logging
import math

import numpy as np

from microcircuit_lab.builder_tools.constant_current import compensate_lost_mean_input
from microcircuit_lab.config.connectivity import SHARED_DISTRIBUTIONS, SHARED_RULES
from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.config.scaling import ScalingRecord

logger = logging.getLogger(__name__)


def scale_network(
    network: NetworkConfig,
    *,
    N_scaling: float,
    K_scaling: float,
    scaled_from: str,
    preserve_mean_input: bool = True,
    preserve_variance: bool = True,
    compensate_recurrent_input: bool = True,
) -> NetworkConfig:
    """
    Return ``network`` scaled down, as the files of the scaled network show it.

    1. The number of neurons of each population times ``N_scaling``.
    2. The synapses per neuron times ``K_scaling``: the number each
       connection rule takes (see :func:`scale_rule_number`) and the
       background indegrees.
    3. The weights divided by ``sqrt(K_scaling)`` (``preserve_variance``,
       which keeps the fluctuations of the input) or by ``K_scaling`` (which
       keeps its mean), for connections and background inputs.
    4. With ``preserve_variance`` and ``preserve_mean_input``: a constant
       current added to each neuron's ``I_e``, the mean input lost in step 3
       (van Albada, Helias & Diesmann 2015). The lost background input
       always; the lost recurrent input too with ``compensate_recurrent_input``,
       from ``reference.full_mean_rates``.

    Stimuli are not scaled. A network that was already scaled is refused: its
    compensation would take the first one's currents as the full input.

    Parameters
    ----------
    network
        The network as written, at full scale (e.g. from
        :func:`~microcircuit_lab.network.load.read_network`).
    N_scaling, K_scaling
        The factors, above 0 (1 keeps that number).
    scaled_from
        The name of the full-scale network, written in the record.
    preserve_mean_input, preserve_variance, compensate_recurrent_input
        As above.

    Returns
    -------
    NetworkConfig
        The scaled network; its ``scaling`` records how it was made (written
        as ``scaling.yaml``, never applied).

    Raises
    ------
    ValueError
        If ``network`` was already scaled; if a population would have no
        neuron left; if a connection's rule cannot be scaled; if the current
        for recurrent connections is added (``preserve_variance``,
        ``preserve_mean_input`` and ``compensate_recurrent_input``, with
        ``K_scaling`` not 1) and a connection's weight distribution is not a
        shared one; or, to add the current, if a weight is not in pA on the
        default receptor port.
    """

    if network.scaling is not None:
        raise ValueError(
            f"This network was already scaled (from {network.scaling.scaled_from!r}); scale the "
            "full-scale network instead, with the product of the factors."
        )
    # The record of this scaling: this function and its arguments. A copy of
    # this function in a project records itself, by its module's name.
    record = ScalingRecord(
        scaled_from=scaled_from,
        scaled_with=f"{__name__}.scale_network",
        parameters={
            "N_scaling": N_scaling,
            "K_scaling": K_scaling,
            "preserve_mean_input": preserve_mean_input,
            "preserve_variance": preserve_variance,
            "compensate_recurrent_input": compensate_recurrent_input,
        },
    )

    scaled = _scale_neuron_numbers(network, N_scaling)
    # The current for recurrent connections needs the real mean of every weight.
    needs_weight_means = (
        preserve_variance and preserve_mean_input and compensate_recurrent_input and K_scaling != 1.0
    )
    scaled = _scale_indegrees(scaled, N_scaling, K_scaling, needs_weight_means)
    scaled = scale_weights(scaled, K_scaling, preserve_variance)
    scaled = compensate_lost_mean_input(
        scaled,
        network,
        K_scaling,
        preserve_mean_input=preserve_mean_input,
        preserve_variance=preserve_variance,
        compensate_recurrent_input=compensate_recurrent_input,
    )
    return scaled.model_copy(update={"scaling": record})


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


def scale_weights(network: NetworkConfig, K_scaling: float, preserve_variance: bool) -> NetworkConfig:
    """
    Scale the weights of all recurrent connections and background inputs for
    ``K_scaling``.

    ``preserve_variance`` selects the law:

    - True (default): ``w / sqrt(K_scaling)``, as in van Albada, Helias &
      Diesmann (2015), PLoS Comput Biol 11:e1004490. This keeps the
      fluctuations of the input but changes its mean. The step
      ``compensate_lost_mean_input`` restores the mean with a constant current
      if ``preserve_mean_input`` is also true.
    - False: ``w / K_scaling``. This keeps the mean input (indegree times
      weight does not change) but not the fluctuations, and needs no
      compensation.
    """

    divisor = math.sqrt(K_scaling) if preserve_variance else K_scaling

    # Recurrent connections: the whole weight column at once.
    connections = network.connections.with_columns(copy=False, **{
        "weight.mean": network.connections["weight.mean"] / divisor
    })

    # Background Poisson input.
    poisson_background = {}

    for pop_name, input_cfg in network.poisson_background.items():
        mean = input_cfg.weight.mean / divisor
        weight = input_cfg.weight.model_copy(update={"mean": mean})
        poisson_background[pop_name] = input_cfg.model_copy(update={"weight": weight})

    return network.model_copy(
        update={"connections": connections, "poisson_background": poisson_background}
    )


def _scale_neuron_numbers(network: NetworkConfig, N_scaling: float) -> NetworkConfig:
    """
    Multiply the size of each population by ``N_scaling``, rounded to a whole
    number of neurons.
    """

    populations = {}

    for name, population in network.populations.items():
        scaled_size = int(round(population.size * N_scaling))
        if scaled_size < 1:
            raise ValueError(
                f"N_scaling={N_scaling} reduces population "
                f"'{name}' from {population.size} neurons to zero. "
                "Increase N_scaling to keep every configured population non-empty."
            )

        populations[name] = population.model_copy(update={"size": scaled_size})

    return network.model_copy(update={"populations": populations})


def _scale_indegrees(
    network: NetworkConfig, N_scaling: float, K_scaling: float, needs_weight_means: bool
) -> NetworkConfig:
    """
    Multiply the background indegrees by ``K_scaling`` and scale the number
    each connection rule takes (see :func:`scale_rule_number`). Weights and
    the constant currents are scaled in later steps.
    """

    # Scale the background indegrees.
    poisson_background = {
        name: entry.model_copy(update={"indegree": entry.indegree * K_scaling})
        for name, entry in network.poisson_background.items()
    }

    # Scale the number each connection rule takes (n_synapses, indegree, ...),
    # for all connections at once.
    table = network.connections
    rule = table["rule"]
    _check_connections_can_scale(table, N_scaling, K_scaling, needs_weight_means)
    scaled = scale_rule_number(table["number"], rule, N_scaling, K_scaling)

    too_likely = np.flatnonzero((rule == "pairwise_bernoulli") & (scaled > 1.0))
    if too_likely.size:
        i = too_likely[0]
        raise ValueError(
            f"Connection {table['source'][i]} -> {table['target'][i]}: with N_scaling="
            f"{N_scaling} and K_scaling={K_scaling}, p={table['number'][i]} "
            f"becomes {scaled[i]:.3g}, above 1. Keeping the indegree in smaller populations "
            "needs a higher probability; increase N_scaling or lower K_scaling."
        )

    # A connection scaled to no synapse is left out; say which.
    lost = np.flatnonzero((scaled == 0) & (table["number"] != 0))
    if lost.size:
        names = [f"{table['source'][i]} -> {table['target'][i]}" for i in lost[:5]]
        logger.warning(
            "Scaling left out %d connection(s) with no synapse left: %s%s",
            lost.size, ", ".join(names), ", ..." if lost.size > 5 else "",
        )
    connections = table.with_columns(copy=False, number=scaled).keep_rows(scaled != 0)

    return network.model_copy(update={"poisson_background": poisson_background, "connections": connections})


def _check_connections_can_scale(
    table, N_scaling: float, K_scaling: float, needs_weight_means: bool
) -> None:
    """
    Raise for a connection that scaling cannot keep at the full-scale input.
    Its rule cannot keep each neuron's inputs at ``K_scaling`` times the
    full-scale number: ``one_to_one`` always gives one input, ``all_to_all``
    gives ``n_source``, which shrinks with ``N_scaling``, and a rule that is not
    shared says nothing about its scaling. Or, if ``needs_weight_means``, its
    weights come from a project distribution, whose real mean, which the
    compensation needs, is not known here. (A project delay distribution is fine: scaling leaves delays alone.)
    """

    rule = table["rule"]
    reasons = (
        ((rule == "one_to_one") & (K_scaling != 1.0),
         "one_to_one gives each neuron one input at any scale, so K_scaling must be 1"),
        ((rule == "all_to_all") & (K_scaling != N_scaling),
         "all_to_all gives each neuron n_source inputs, which shrink with N_scaling, so "
         "K_scaling must equal N_scaling"),
        (~np.isin(rule, SHARED_RULES),
         "rule {rule} is not a shared one, and how it scales is not known"),
        (needs_weight_means & ~np.isin(table["weight.distribution"], SHARED_DISTRIBUTIONS),
         "the real mean of weights from a project distribution, which the compensation "
         "needs, is not known"),
    )
    for rows, why in reasons:
        if rows.any():
            i = int(np.flatnonzero(rows)[0])
            raise ValueError(
                f"Connection {table['source'][i]} -> {table['target'][i]} (N_scaling={N_scaling}, "
                f"K_scaling={K_scaling}): " + why.format(rule=repr(rule[i])) + "."
            )
