"""
Parameter derivation.

This module derives simulator-ready parameters from the biological
network description while preserving the original immutable
configuration.
"""

from __future__ import annotations

import numpy as np

from microcircuit_lab.config.network import (
    NetworkConfig,
)

from microcircuit_lab.network.scaling import (
    scale_neuron_number,
    scale_synapse_number,
    scale_weights,
    background_compensation_current,
    background_dc_current,
    network_compensation_current,
)

from microcircuit_lab.network.parameters import (
    indegree_matrix,
    full_mean_rates,
    background_indegrees,
    background_psc_weights,
    mean_psc_matrix,
    synaptic_tau,
    convert_network_psp_to_psc,
    network_mean_input,
)


class NetworkPreprocessor:
    """
    Build a derived NetworkConfig.
    """

    def __init__(
        self,
        network_config: NetworkConfig,
    ) -> None:
        self._network_config = network_config

    def process(self) -> NetworkConfig:
        """
        Build a derived NetworkConfig.

        The returned object is independent from the original one.
        """

        network = self._network_config.model_copy(deep=True)
        network = convert_network_psp_to_psc(network)

        if network.scaling.is_scaled:
            network = self._apply_n_scaling(network)
            network = self._apply_k_scaling(network)
            network = scale_weights(network)
            network = self._apply_scaling_compensation(network)

        network = self._apply_background_poisson_rates(network)
        network = self._apply_background_dc_current(network)

        return network

    def _apply_n_scaling(
        self,
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

    def _apply_k_scaling(
        self,
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

    def _apply_background_poisson_rates(
        self,
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

    def _apply_scaling_compensation(
        self,
        network: NetworkConfig,
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
        "dc": _apply_background_dc_current replaces the background
        Poisson drive entirely with a DC current sized for the full
        (unscaled) biological input, so no separate scaling-bias
        correction for it is needed -- adding both would double-count.
        """

        # Original network quantities
        original = self._network_config
        scaling = original.scaling

        if not scaling.preserve_variance or not scaling.preserve_mean_input:
            return network

        if original.reference is None or scaling.K_scaling == 1.0:
            return network

        # Connection indegrees for recurrent and background connections
        indegrees = indegree_matrix(original)
        K_ext = background_indegrees(original)

        # Mean PSC amplitudes (pA) for recurrent and background connections
        PSC_ext = background_psc_weights(original)
        PSC_matrix = mean_psc_matrix(original)

        # Synaptic time constant (ms) of each input: the target's tau_syn_ex
        # for excitatory inputs, its tau_syn_in for inhibitory ones.
        tau_matrix = synaptic_tau(original, PSC_matrix)
        tau_ext = synaptic_tau(original, PSC_ext)

        # Compute recurrent contribution when requested.
        network_current = np.zeros(len(original.populations))

        if scaling.compensate_recurrent_input:
            mean_rates = full_mean_rates(original)

            # The input is weighted by each connection's own time constant
            # (pA ms), so the compensation takes no further tau_syn.
            network_input = network_mean_input(
                mean_PSC_matrix=PSC_matrix * tau_matrix,
                indegree_matrix=indegrees,
                mean_rates=mean_rates,
            )

            network_current = network_compensation_current(
                network_input=network_input,
                tau_syn=1.0,
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

    def _apply_background_dc_current(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        """
        Replace the background Poisson drive with an equivalent constant
        current, per Potjans & Diesmann (2014)'s comparison of Poisson vs.
        DC background input (their Fig. 5). No-op unless background_mode
        is "dc".

        The DC amplitude is the mean current a full-strength (unscaled)
        background Poisson process would deliver on average -- computed
        from the original biological network, exactly like the
        compensation currents in _apply_scaling_compensation, so the
        result is independent of any N/K scaling applied to the recurrent
        network. Background rates are zeroed out afterwards so no Poisson
        generator ends up created for them (see NestBackend).
        """

        if network.background_mode != "dc":
            return network

        original = self._network_config

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
