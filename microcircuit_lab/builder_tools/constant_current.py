"""
Constant currents: the steps that add a constant current to ``I_e``.

``compensate_lost_mean_input`` replaces the mean input that scaling removes
(a step of :func:`~microcircuit_lab.builder_tools.scaling.scale_network`, from the
full-scale network ``original``); ``replace_background_by_mean_current``
replaces the background Poisson input by a constant current of the same mean
(a step a builder applies before writing the network). The
formula of these currents is :func:`mean_current`, at the end of the file.

It assumes current-based synapses with exponential currents: a spike of
amplitude ``weight`` (pA) and time constant ``tau_syn`` (ms) carries a charge
of ``0.001 * tau_syn * weight`` (pA x s).
"""

from __future__ import annotations

import numpy as np

from microcircuit_lab.builder_tools.mean_input import (
    background_indegrees,
    background_rates,
    background_weights,
    full_mean_rates,
    indegree_matrix,
    mean_psc_matrix,
    synaptic_tau,
    tau_syn_ex,
    tau_syn_in,
)
from microcircuit_lab.config.network import NetworkConfig


def compensate_lost_mean_input(
    network: NetworkConfig,
    original: NetworkConfig,
    K_scaling: float,
    *,
    preserve_mean_input: bool,
    preserve_variance: bool,
    compensate_recurrent_input: bool,
) -> NetworkConfig:
    """
    Add the constant currents that replace the mean input lost by scaling.

    Needed only for variance-preserving (square-root) weight scaling; linear
    scaling keeps the mean. Whether it runs is set by ``preserve_variance``
    and ``preserve_mean_input`` (the latter turns compensation on or off);
    ``compensate_recurrent_input`` decides whether the recurrent input
    is compensated too. The background input is always compensated; if
    :func:`replace_background_by_mean_current` follows, it computes its current
    from the scaled background, which this one completes to the full-scale mean.
    """

    if not preserve_variance or not preserve_mean_input:
        return network

    if K_scaling == 1.0:
        return network

    network_current = np.zeros(len(original.populations))
    if compensate_recurrent_input:
        network_current = _recurrent_compensation(original, K_scaling)

    return _add_to_I_e(network, network_current + _background_compensation(original, K_scaling))


def _recurrent_compensation(original: NetworkConfig, K_scaling: float) -> np.ndarray:
    """
    The DC current (pA) per population that replaces the mean recurrent input
    lost by scaling, from the full-scale network ``original``: weights times
    1/sqrt(K_scaling) and indegrees times K_scaling keep sqrt(K_scaling) of the
    mean, so (1 - sqrt(K_scaling)) of it is added back.

    Raises if a connection's mean current is not known (see
    _mean_current_is_known).
    """

    table = original.connections
    known = _connections_with_known_current(original)
    if not known.all():
        i = int(np.flatnonzero(~known)[0])
        raise ValueError(
            f"The mean input lost by scaling is known only for weights in pA on the default "
            f"receptor port; connection {table['source'][i]} -> {table['target'][i]} has "
            f"unit {table['weight.unit'][i]} or another port. Set preserve_mean_input or "
            "compensate_recurrent_input to false, or preserve_variance to false (no current needed)."
        )

    mean_rates = full_mean_rates(original)
    current = np.zeros(len(original.populations))

    # Excitatory and inhibitory input have different synaptic time
    # constants, so each kind is compensated with its own.
    weight = table["weight.mean"]
    excitatory = known & (weight > 0)
    inhibitory = known & (weight < 0)
    names = list(original.populations)
    for rows, tau_syn in ((excitatory, tau_syn_ex), (inhibitory, tau_syn_in)):
        if not rows.any():
            continue
        part = original.model_copy(update={"connections": table.keep_rows(rows)})
        has_input = np.isin(names, table["target"][rows])
        input_per_source = mean_current(
            weight=mean_psc_matrix(part),
            indegree=indegree_matrix(part),
            rate=mean_rates,
            tau_syn=tau_syn(original, needed=has_input)[:, np.newaxis],
        )
        current += (1.0 - np.sqrt(K_scaling)) * input_per_source.sum(axis=1)

    return current


def _background_compensation(original: NetworkConfig, K_scaling: float) -> np.ndarray:
    """
    The DC current (pA) per population that replaces the mean background
    input lost by scaling, from the full-scale network ``original``.

    Raises if a background input's mean current is not known (see
    _mean_current_is_known).
    """

    unknown = _background_without_known_current(original)
    if unknown:
        raise ValueError(
            f"The mean input lost by scaling is known only for weights in pA on the default "
            f"receptor port; the background input of {unknown} has another unit or port. Set "
            "preserve_mean_input to false, or preserve_variance to false (no current needed)."
        )

    weight = background_weights(original)
    current = mean_current(
        weight=weight,
        indegree=background_indegrees(original),
        rate=background_rates(original),
        tau_syn=synaptic_tau(original, weight),
    )
    return (1.0 - np.sqrt(K_scaling)) * current


def replace_background_by_mean_current(network: NetworkConfig) -> NetworkConfig:
    """
    Replace the background Poisson input by a constant current of the same mean.

    The current (pA) is the mean of the background input as the network gives
    it (rate per synapse, indegree, weight), added to ``I_e`` (see Potjans &
    Diesmann 2014, Fig. 5). The returned network has no background input left:
    ``poisson_background`` is empty.

    Parameters
    ----------
    network
        The network, with its background weights in pA on the default receptor
        port.

    Returns
    -------
    NetworkConfig
        A new network without background input.
    """

    unknown = _background_without_known_current(network)
    if unknown:
        raise ValueError(
            f"The mean background current is known only for weights in pA on the default "
            f"receptor port; the background input of {unknown} has another unit or uses "
            "another port."
        )

    weight = background_weights(network)
    dc_current = mean_current(
        weight=weight,
        indegree=background_indegrees(network),
        rate=background_rates(network),
        tau_syn=synaptic_tau(network, weight),
    )

    network = _add_to_I_e(network, dc_current)
    return network.model_copy(update={"poisson_background": {}})


def _add_to_I_e(network: NetworkConfig, current: np.ndarray) -> NetworkConfig:
    """Add ``current`` (pA, one value per population, in order) to the ``I_e`` of
    its neuron. A population with nothing to add keeps its ``I_e`` as it is,
    also unset, so a model without ``I_e`` works when it needs no current."""

    populations = {}
    for added, (name, population) in zip(current, network.populations.items()):
        parameters = population.neuron.parameters
        if added == 0.0:
            populations[name] = population
            continue
        parameters = parameters.model_copy(update={"I_e": (parameters.I_e or 0.0) + float(added)})
        neuron = population.neuron.model_copy(update={"parameters": parameters})
        populations[name] = population.model_copy(update={"neuron": neuron})
    return network.model_copy(update={"populations": populations})


def _mean_current_is_known(network: NetworkConfig, item) -> bool:
    """
    Whether the core knows the mean current of a connection, background input
    or stimulus: its weight is a current (pA) and it reaches the default
    receptor port, whose synaptic time constants are tau_syn_ex and
    tau_syn_in. Another unit (e.g. a conductance in nS) or another port has no
    current the core can compute.
    """

    return item.weight.unit == "pA" and network.receptor_port(item.synapse) is None


def _connections_with_known_current(network: NetworkConfig) -> np.ndarray:
    """``_mean_current_is_known`` for every connection at once (one bool per row)."""

    table = network.connections
    # The synapse column holds None for the default synapse, which np.unique
    # cannot sort: look up each distinct name once, with None as "".
    synapse = np.where(np.equal(table["synapse"], None), "", table["synapse"]).astype(str)
    names, inverse = np.unique(synapse, return_inverse=True)
    on_default_port = np.asarray(
        [network.receptor_port(name or None) is None for name in names], dtype=bool
    )
    return (table["weight.unit"] == "pA") & on_default_port[inverse]


def _background_without_known_current(network: NetworkConfig) -> list[str]:
    """The populations whose background input has no known mean current."""

    return [
        name
        for name, input_cfg in network.poisson_background.items()
        if not _mean_current_is_known(network, input_cfg)
    ]


def mean_current(
    weight: np.ndarray,
    indegree: np.ndarray,
    rate: np.ndarray,
    tau_syn: np.ndarray,
) -> np.ndarray:
    """
    The constant current (pA) with the mean of the input of ``indegree``
    synapses of amplitude ``weight`` (pA) firing at ``rate`` (spikes/s).

    One spike gives an exponential current of amplitude ``weight`` and time
    constant ``tau_syn`` (ms), a charge of ``tau_syn * weight`` (ms x pA); the
    factor 0.001 turns it into pA x s. This assumes current-based synapses
    with exponential currents (``tau_syn_ex``, ``tau_syn_in``).
    """

    return 0.001 * tau_syn * weight * indegree * rate
