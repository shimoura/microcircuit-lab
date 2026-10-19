"""
The steps of :func:`prepare_network` that add constant currents to ``I_e``.

``compensate_lost_mean_input`` replaces the mean input that scaling removes;
``replace_background_by_mean_current`` replaces the background Poisson input by
a constant current. Both take the full-scale network (``original``), because the
currents are those of the biological input, whatever the scaling.
"""

from __future__ import annotations

import logging

import numpy as np

from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.network.quantities import (
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
from microcircuit_lab.network.scaling import (
    background_compensation_current,
    background_dc_current,
    network_compensation_current,
)

logger = logging.getLogger(__name__)


def compensate_lost_mean_input(
    network: NetworkConfig,
    original: NetworkConfig,
) -> NetworkConfig:
    """
    Apply constant current compensation to account for the change in mean synaptic
    input due to synapse scaling.

    Only meaningful when scale_weights() used the variance-preserving
    (sqrt) law -- the mean-preserving (linear) law introduces no bias
    to compensate for in the first place. Governed by
    scaling.preserve_variance and scaling.preserve_mean_input (the
    master switch for compensation); scaling.compensate_recurrent_input
    additionally includes/excludes just the recurrent contribution.

    The background contribution is skipped when background_mode is
    "mean_current": replace_background_by_mean_current replaces the background
    Poisson drive entirely with a DC current sized for the full
    (unscaled) biological input, so no separate scaling-bias
    correction for it is needed -- adding both would double-count.
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
    Replace the background Poisson drive with an equivalent constant
    current, per Potjans & Diesmann (2014)'s comparison of Poisson vs.
    DC background input (their Fig. 5). No-op unless background_mode
    is "mean_current".

    The DC amplitude is the mean current a full-strength (unscaled)
    background Poisson process would deliver on average -- computed
    from the original biological network, exactly like the
    compensation currents in compensate_lost_mean_input, so the
    result is independent of any N/K scaling applied to the recurrent
    network. Background rates are zeroed out afterwards so no Poisson
    generator ends up created for them (the backend skips them).
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
    """Add ``current`` (pA, one value per population, in order) to the
    ``I_e`` of each population's neuron."""

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
