"""
Prepare a network for the simulation: the steps between the network as
written in the files and the network the simulator builds.

:func:`prepare_network` lists the steps in order. Each step is a small
function below that takes a :class:`NetworkConfig` and returns a new one;
nothing is changed in place. To add a step (e.g. a new compensation rule),
write its function here and call it from :func:`prepare_network`.
"""

from __future__ import annotations

import logging

import numpy as np

from microcircuit_lab.config.connectivity import RULE_NUMBER
from microcircuit_lab.config.network import NetworkConfig

from microcircuit_lab.network.scaling import (
    scale_neuron_number,
    scale_rule_number,
    scale_weights,
    background_compensation_current,
    background_dc_current,
    network_compensation_current,
)

from microcircuit_lab.network.quantities import (
    indegree_matrix,
    full_mean_rates,
    background_indegrees,
    background_psc_weights,
    mean_psc_matrix,
    synaptic_tau,
    tau_syn_ex,
    tau_syn_in,
    convert_network_psp_to_psc,
    network_mean_input,
)


logger = logging.getLogger(__name__)


def prepare_network(config: NetworkConfig) -> NetworkConfig:
    """
    Return the network ready to simulate; ``config`` itself is not changed.

    The steps, in order:

    1. convert ``unit: PSP`` weights (mV) to currents (pA), with each target
       population's own neuron parameters;
    2. if ``scaling`` asks for it: scale the neuron numbers (``N_scaling``),
       the indegrees (``K_scaling``) and the weights, then add the DC current
       that compensates the mean input lost by scaling (for current weights,
       PSP or PSC, on the default receptor port: the only input whose mean
       current is known);
    3. turn each population's background rate per synapse into the rate of
       its Poisson generator (rate x indegree);
    4. with ``background_mode: mean_current``, replace the background input by a
       constant current of the same mean.

    Parameters
    ----------
    config
        The network as read from its files (see
        :func:`microcircuit_lab.network.load.read_network`).

    Returns
    -------
    NetworkConfig
        A new network description with currents in pA, scaled sizes and
        indegrees, and the compensation currents added to ``I_e``.
    """

    network = convert_network_psp_to_psc(config.model_copy(deep=True))

    if network.scaling.is_scaled:
        network = _scale_neuron_numbers(network)
        network = _scale_indegrees(network)
        network = scale_weights(network)
        network = _compensate_lost_mean_input(network, original=config)

    network = _background_rate_per_neuron(network)
    network = _replace_background_by_mean_current(network, original=config)

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

    return network.model_copy(
        update={
            "populations": populations,
        }
    )


def _scale_indegrees(
    network: NetworkConfig,
) -> NetworkConfig:
    """
    Apply indegree scaling.

    Currently scales:
        - the number each connection rule takes (see scale_rule_number)
        - background indegrees

    Synaptic weights and DC compensation are intentionally
    handled in later transformations.
    """

    scaling = network.scaling

    # Scale background indegrees
    populations = {}
    for name, population in network.populations.items():
        populations[name] = population.model_copy(
            update={
                "background_indegree": (
                    population.background_indegree * scaling.K_scaling
                )
            }
        )

    # Scale the number each connection rule takes (n_synapses, indegree, ...)
    connections = []
    for connection in network.connections:
        scaled = scale_rule_number(
            connection.number,
            connection.rule,
            scaling.N_scaling,
            scaling.K_scaling,
        )
        if scaled == 0:
            continue
        if connection.rule == "pairwise_bernoulli" and scaled > 1.0:
            raise ValueError(
                f"Connection {connection.source} -> {connection.target}: with N_scaling="
                f"{scaling.N_scaling} and K_scaling={scaling.K_scaling}, p={connection.p} "
                f"becomes {scaled:.3g}, above 1. Keeping the indegree in smaller populations "
                "needs a higher probability; increase N_scaling or lower K_scaling."
            )

        connections.append(
            connection.model_copy(update={RULE_NUMBER[connection.rule]: scaled})
        )

    return network.model_copy(
        update={
            "populations": populations,
            "connections": connections,
        }
    )


def _compensate_lost_mean_input(
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
    "mean_current": _replace_background_by_mean_current replaces the background
    Poisson drive entirely with a DC current sized for the full
    (unscaled) biological input, so no separate scaling-bias
    correction for it is needed -- adding both would double-count.
    """
    scaling = original.scaling

    if not scaling.preserve_variance or not scaling.preserve_mean_input:
        return network

    if scaling.K_scaling == 1.0:
        return network

    if original.reference is None:
        logger.warning(
            "Scaled network without reference.full_mean_rates: no DC compensation "
            "is applied. Add the full-scale mean rates to reference.yaml to "
            "compensate the lost mean input."
        )
        return network

    network_current = np.zeros(len(original.populations))
    if scaling.compensate_recurrent_input:
        network_current = _recurrent_compensation(original)

    background_current = np.zeros(len(original.populations))
    if original.background_mode != "mean_current":
        background_current = _background_compensation(original)

    pop_names = list(original.populations.keys())

    # Apply the compensation currents to neurons
    populations = {}
    for i, name in enumerate(pop_names):
        population = network.populations[name]
        params = population.neuron.parameters.model_copy(
            update={
                "I_e": (
                    population.neuron.parameters.I_e
                    + network_current[i]
                    + background_current[i]
                )
            }
        )

        neuron = population.neuron.model_copy(
            update={
                "parameters": params,
            }
        )

        populations[name] = population.model_copy(
            update={
                "neuron": neuron,
            }
        )

    return network.model_copy(
        update={
            "populations": populations,
        }
    )


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

    bg_rates = np.asarray(
        [original.background_inputs[name].rate for name in pop_names],
        dtype=float,
    )
    return background_compensation_current(
        PSC_ext=PSC_ext,
        K_ext=background_indegrees(original),
        bg_rate=bg_rates,
        tau_syn=synaptic_tau(original, PSC_ext),
        K_scaling=original.scaling.K_scaling,
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

        background_inputs[pop_name] = input_cfg.model_copy(
            update={
                "rate": input_cfg.rate * K_ext,
            }
        )

    return network.model_copy(
        update={
            "background_inputs": background_inputs,
        }
    )


def _replace_background_by_mean_current(
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
    compensation currents in _compensate_lost_mean_input, so the
    result is independent of any N/K scaling applied to the recurrent
    network. Background rates are zeroed out afterwards so no Poisson
    generator ends up created for them (see NestBackend).
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

    pop_names = list(original.populations.keys())
    bg_rates = np.asarray(
        [original.background_inputs[name].rate for name in pop_names],
        dtype=float,
    )

    dc_current = background_dc_current(
        PSC_ext=PSC_ext,
        K_ext=K_ext,
        bg_rate=bg_rates,
        tau_syn=tau_syn,
    )

    populations = {}
    background_inputs = {}

    for i, name in enumerate(pop_names):
        population = network.populations[name]
        params = population.neuron.parameters.model_copy(
            update={
                "I_e": population.neuron.parameters.I_e + dc_current[i],
            }
        )

        neuron = population.neuron.model_copy(
            update={
                "parameters": params,
            }
        )

        populations[name] = population.model_copy(
            update={
                "neuron": neuron,
            }
        )

        background_inputs[name] = network.background_inputs[name].model_copy(
            update={"rate": 0.0}
        )

    return network.model_copy(
        update={
            "populations": populations,
            "background_inputs": background_inputs,
        }
    )


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
