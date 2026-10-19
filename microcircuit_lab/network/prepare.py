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

from microcircuit_lab.config.network import NetworkConfig

from microcircuit_lab.network.scaling import (
    scale_neuron_number,
    scale_synapse_number,
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
       that compensates the mean input lost by scaling;
    3. turn each population's background rate per synapse into the rate of
       its Poisson generator (rate x indegree);
    4. with ``background_mode: dc``, replace the background input by a
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
    network = _replace_background_by_dc(network, original=config)

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
        - recurrent synapse numbers
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

    # Scale recurrent synapse numbers
    connections = []
    for connection in network.connections:
        scaled_n_synapses = scale_synapse_number(
            connection.n_synapses,
            scaling.N_scaling * scaling.K_scaling,
        )
        if scaled_n_synapses < 1:
            continue

        connections.append(
            connection.model_copy(update={"n_synapses": scaled_n_synapses})
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
    "dc": _replace_background_by_dc replaces the background
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

    # Connection indegrees for recurrent and background connections
    indegrees = indegree_matrix(original)
    K_ext = background_indegrees(original)

    # Mean PSC amplitudes (pA) for recurrent and background connections
    PSC_ext = background_psc_weights(original)
    PSC_matrix = mean_psc_matrix(original)

    # Synaptic time constant (ms) of the background input of each
    # population: tau_syn_ex if its weight is excitatory, tau_syn_in if
    # it is inhibitory.
    tau_ext = synaptic_tau(original, PSC_ext)

    # Compute recurrent contribution when requested.
    network_current = np.zeros(len(original.populations))

    if scaling.compensate_recurrent_input:
        mean_rates = full_mean_rates(original)

        # Excitatory and inhibitory input have different synaptic time
        # constants, so each kind is compensated with its own.
        excitatory_PSC = np.where(PSC_matrix > 0, PSC_matrix, 0.0)
        inhibitory_PSC = np.where(PSC_matrix < 0, PSC_matrix, 0.0)

        network_current = network_compensation_current(
            network_input=network_mean_input(
                mean_PSC_matrix=excitatory_PSC,
                indegree_matrix=indegrees,
                mean_rates=mean_rates,
            ),
            tau_syn=tau_syn_ex(original),
            K_scaling=scaling.K_scaling,
        )

        if inhibitory_PSC.any():
            network_current += network_compensation_current(
                network_input=network_mean_input(
                    mean_PSC_matrix=inhibitory_PSC,
                    indegree_matrix=indegrees,
                    mean_rates=mean_rates,
                ),
                tau_syn=tau_syn_in(original),
                K_scaling=scaling.K_scaling,
            )

    # Compute background contribution to DC compensation from biological network quantities
    pop_names = list(original.populations.keys())
    background_current = np.zeros(len(original.populations))

    if original.background_mode != "dc":
        bg_rates = np.asarray(
            [original.background_inputs[name].rate for name in pop_names],
            dtype=float,
        )
        background_current = background_compensation_current(
            PSC_ext=PSC_ext,
            K_ext=K_ext,
            bg_rate=bg_rates,
            tau_syn=tau_ext,
            K_scaling=scaling.K_scaling,
        )

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


def _replace_background_by_dc(
    network: NetworkConfig,
    original: NetworkConfig,
) -> NetworkConfig:
    """
    Replace the background Poisson drive with an equivalent constant
    current, per Potjans & Diesmann (2014)'s comparison of Poisson vs.
    DC background input (their Fig. 5). No-op unless background_mode
    is "dc".

    The DC amplitude is the mean current a full-strength (unscaled)
    background Poisson process would deliver on average -- computed
    from the original biological network, exactly like the
    compensation currents in _compensate_lost_mean_input, so the
    result is independent of any N/K scaling applied to the recurrent
    network. Background rates are zeroed out afterwards so no Poisson
    generator ends up created for them (see NestBackend).
    """

    if network.background_mode != "dc":
        return network

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
