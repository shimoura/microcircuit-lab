"""
The steps of :func:`prepare_network` that add constant currents to ``I_e``.

``compensate_lost_mean_input`` replaces the mean input that scaling removes;
``replace_background_by_mean_current`` replaces the background Poisson input by
a constant current. Both take the full-scale network (``original``), because the
currents are those of the biological input, whatever the scaling. The formulas
of these currents are at the end of the file.
"""

from __future__ import annotations

import logging

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

logger = logging.getLogger(__name__)


def compensate_lost_mean_input(
    network: NetworkConfig,
    original: NetworkConfig,
) -> NetworkConfig:
    """
    Add the constant currents that replace the mean input lost by scaling.

    Needed only for variance-preserving (square-root) weight scaling; linear
    scaling keeps the mean. Whether it runs is set by ``scaling.preserve_variance``
    and ``scaling.preserve_mean_input`` (the latter turns compensation on or off);
    ``scaling.compensate_recurrent_input`` decides whether the recurrent input
    is compensated too.

    With ``background_mode: mean_current`` the background input is not
    compensated here, because ``replace_background_by_mean_current`` already
    replaces it by a current for the full-scale input. Doing both would count it
    twice.
    """
    scaling = original.scaling

    if not scaling.preserve_variance or not scaling.preserve_mean_input:
        return network

    if scaling.K_scaling == 1.0:
        return network

    network_current = np.zeros(len(original.populations))
    if scaling.compensate_recurrent_input:
        network_current = _recurrent_compensation(original)

    background_current = np.zeros(len(original.populations))
    if original.background_mode != "mean_current":
        background_current = _background_compensation(original)

    return _add_to_I_e(network, network_current + background_current)


def _recurrent_compensation(original: NetworkConfig) -> np.ndarray:
    """
    The DC current (pA) per population that replaces the mean recurrent input
    lost by scaling, from the full-scale network ``original``.

    Only connections whose mean current is known are compensated (see
    _mean_current_is_known).
    """

    known = [c for c in original.connections if _mean_current_is_known(original, c)]
    unknown = [
        f"{c.source} -> {c.target}"
        for c in original.connections
        if not _mean_current_is_known(original, c)
    ]
    if unknown:
        logger.warning(
            "The input lost by scaling is not compensated for %s: their weights are "
            "native (e.g. conductances) or reach another receptor port than the default.",
            ", ".join(unknown),
        )

    mean_rates = full_mean_rates(original)
    current = np.zeros(len(original.populations))

    # Excitatory and inhibitory input have different synaptic time
    # constants, so each kind is compensated with its own.
    excitatory = [c for c in known if c.weight.mean > 0]
    inhibitory = [c for c in known if c.weight.mean < 0]
    for connections, tau_syn in ((excitatory, tau_syn_ex), (inhibitory, tau_syn_in)):
        if not connections:
            continue
        part = original.model_copy(update={"connections": connections})
        network_input = network_mean_input(
            mean_PSC_matrix=mean_psc_matrix(part),
            indegree_matrix=indegree_matrix(part),
            mean_rates=mean_rates,
        )
        current += network_compensation_current(
            network_input=network_input,
            tau_syn=tau_syn(original, needed=network_input != 0),
            K_scaling=original.scaling.K_scaling,
        )

    return current


def _background_compensation(original: NetworkConfig) -> np.ndarray:
    """
    The DC current (pA) per population that replaces the mean background
    input lost by scaling, from the full-scale network ``original``; 0 for a
    population whose background input has no known mean current (see
    _mean_current_is_known).
    """

    pop_names = list(original.populations.keys())
    PSC_ext = background_psc_weights(original)

    unknown = _background_without_known_current(original)
    if unknown:
        logger.warning(
            "The background input lost by scaling is not compensated for %s: its weight "
            "is native (e.g. a conductance) or reaches another receptor port than the default.",
            ", ".join(unknown),
        )
        PSC_ext = np.where(np.isin(pop_names, unknown), 0.0, PSC_ext)

    return background_compensation_current(
        PSC_ext=PSC_ext,
        K_ext=background_indegrees(original),
        bg_rate=background_rates(original),
        tau_syn=synaptic_tau(original, PSC_ext),
        K_scaling=original.scaling.K_scaling,
    )


def replace_background_by_mean_current(
    network: NetworkConfig,
    original: NetworkConfig,
) -> NetworkConfig:
    """
    Replace the background Poisson input by a constant current of the same mean.

    Does nothing unless ``background_mode`` is "mean_current" (see Potjans &
    Diesmann 2014, Fig. 5).

    The current is the mean that the full-strength background input delivers.
    It is computed from the original network, as in ``compensate_lost_mean_input``,
    so scaling does not change it. The background rates are then set to 0, so
    the backend creates no Poisson generator for them.
    """

    if network.background_mode != "mean_current":
        return network

    unknown = _background_without_known_current(original)
    if unknown:
        raise ValueError(
            f"background_mode: mean_current needs the mean background current, which is only known "
            f"for current weights (PSP or PSC) on the default receptor port; the background "
            f"input of {unknown} is native or uses another port. Use background_mode: poisson."
        )

    K_ext = background_indegrees(original)
    PSC_ext = background_psc_weights(original)
    tau_syn = synaptic_tau(original, PSC_ext)

    dc_current = background_dc_current(
        PSC_ext=PSC_ext,
        K_ext=K_ext,
        bg_rate=background_rates(original),
        tau_syn=tau_syn,
    )

    network = _add_to_I_e(network, dc_current)
    background_inputs = {
        name: input_cfg.model_copy(update={"rate": 0.0})
        for name, input_cfg in network.background_inputs.items()
    }
    return network.model_copy(update={"background_inputs": background_inputs})


def _add_to_I_e(network: NetworkConfig, current: np.ndarray) -> NetworkConfig:
    """Add ``current`` (pA, one value per population, in order) to the ``I_e`` of its neuron."""

    populations = {}
    for added, (name, population) in zip(current, network.populations.items()):
        parameters = population.neuron.parameters
        parameters = parameters.model_copy(update={"I_e": parameters.I_e + float(added)})
        neuron = population.neuron.model_copy(update={"parameters": parameters})
        populations[name] = population.model_copy(update={"neuron": neuron})
    return network.model_copy(update={"populations": populations})


def _mean_current_is_known(network: NetworkConfig, item) -> bool:
    """
    Whether the core knows the mean current of a connection, background input
    or stimulus: its weight is a current (PSP, converted, or PSC) and it reaches
    the default receptor port, whose synaptic time constants are tau_syn_ex
    and tau_syn_in. A native weight (e.g. a conductance in nS) or another port
    has no current the core can compute.
    """

    return item.weight.unit != "native" and network.receptor_port(item.synapse) is None


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

    The step ``replace_background_by_mean_current`` uses it. It is computed for
    the original, unscaled network, so ``K_scaling`` does not change it.
    """

    return 0.001 * tau_syn * PSC_ext * K_ext * bg_rate
