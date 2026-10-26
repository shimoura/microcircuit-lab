"""
The steps that add constant currents to ``I_e``.

``compensate_lost_mean_input`` replaces the mean input that scaling removes
(a step of :func:`~microcircuit_lab.network.scaling.scale_network`, from the
full-scale network ``original``); ``replace_background_by_mean_current``
replaces the background Poisson input by a constant current of the same mean
(a step of :func:`~microcircuit_lab.network.prepare.prepare_network`). The
formulas of these currents are at the end of the file.
"""

from __future__ import annotations

import numpy as np

from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.network.mean_input import (
    background_indegrees,
    background_psc_weights,
    background_rates,
    full_mean_rates,
    indegree_matrix,
    mean_psc_matrix,
    network_mean_input,
    synaptic_tau,
    tau_syn_ex,
    tau_syn_in,
)


def compensate_lost_mean_input(
    network: NetworkConfig,
    original: NetworkConfig,
    K_scaling: float,
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
    is compensated too. The background input is always compensated, also with
    ``background_mode: mean_current``: its current is then computed from the
    scaled background, which this one completes to the full-scale mean.
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
    lost by scaling, from the full-scale network ``original``.

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
    for rows, tau_syn in ((excitatory, tau_syn_ex), (inhibitory, tau_syn_in)):
        if not rows.any():
            continue
        part = original.model_copy(update={"connections": table.keep_rows(rows)})
        network_input = network_mean_input(
            mean_PSC_matrix=mean_psc_matrix(part),
            indegree_matrix=indegree_matrix(part),
            mean_rates=mean_rates,
        )
        current += network_compensation_current(
            network_input=network_input,
            tau_syn=tau_syn(original, needed=network_input != 0),
            K_scaling=K_scaling,
        )

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

    PSC_ext = background_psc_weights(original)
    return background_compensation_current(
        PSC_ext=PSC_ext,
        K_ext=background_indegrees(original),
        bg_rate=background_rates(original),
        tau_syn=synaptic_tau(original, PSC_ext),
        K_scaling=K_scaling,
    )


def replace_background_by_mean_current(network: NetworkConfig) -> NetworkConfig:
    """
    Replace the background Poisson input by a constant current of the same mean.

    Does nothing unless ``background_mode`` is "mean_current" (see Potjans &
    Diesmann 2014, Fig. 5).

    The current is the mean of the background input as the files give it
    (rate per synapse, indegree, weight). The background rates are then set to
    0, so the backend creates no Poisson generator for them.
    """

    if network.background_mode != "mean_current":
        return network

    unknown = _background_without_known_current(network)
    if unknown:
        raise ValueError(
            f"background_mode: mean_current needs the mean background current, which is only known "
            f"for weights in pA on the default receptor port; the background input of {unknown} "
            "has another unit or uses another port. Use background_mode: poisson."
        )

    K_ext = background_indegrees(network)
    PSC_ext = background_psc_weights(network)
    tau_syn = synaptic_tau(network, PSC_ext)

    dc_current = background_dc_current(
        PSC_ext=PSC_ext,
        K_ext=K_ext,
        bg_rate=background_rates(network),
        tau_syn=tau_syn,
    )

    network = _add_to_I_e(network, dc_current)
    background_inputs = {
        name: input_cfg.model_copy(update={"rate": 0.0})
        for name, input_cfg in network.background_inputs.items()
    }
    return network.model_copy(update={"background_inputs": background_inputs})


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
    ports = {name: network.receptor_port(name) for name in set(table["synapse"].tolist())}
    default_port = np.asarray([ports[name] is None for name in table["synapse"]], dtype=bool)
    return (table["weight.unit"] == "pA") & default_port


def _background_without_known_current(network: NetworkConfig) -> list[str]:
    """The populations whose background input has no known mean current."""

    return [
        name
        for name, input_cfg in network.background_inputs.items()
        if not _mean_current_is_known(network, input_cfg)
    ]


def network_compensation_current(
    network_input: np.ndarray,
    tau_syn: np.ndarray,
    K_scaling: float,
) -> np.ndarray:
    """
    The constant current (pA) that replaces the mean recurrent input lost by
    scaling: weights times 1/sqrt(K_scaling) and indegrees times K_scaling keep
    sqrt(K_scaling) of the mean, so (1 - sqrt(K_scaling)) of it is added back.

    Parameters
    ----------
    network_input
        Mean input to each population from the recurrent network (pA).

    tau_syn
        Synaptic time constant of each population (ms).

    K_scaling
        Indegree scaling factor.

    Returns
    -------
    np.ndarray
        The current for each population (pA).
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
    The constant current (pA) that replaces the mean background input lost by
    scaling, as :func:`network_compensation_current` does for the recurrent
    input: ``bg_rate`` (spikes/s) onto ``K_ext`` synapses of amplitude
    ``PSC_ext`` (pA), with synaptic time constant ``tau_syn`` (ms).
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

    The step ``replace_background_by_mean_current`` uses it.
    """

    return 0.001 * tau_syn * PSC_ext * K_ext * bg_rate
