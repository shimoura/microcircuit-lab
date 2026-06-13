"""
Parameter derivation.

This module derives simulator-ready parameters from the biological
network description while preserving the original immutable
configuration.
"""

from __future__ import annotations

import numpy as np

from human_microcircuit.config.network import (
    NetworkConfig,
)

from human_microcircuit.reference_models.common.scaling import (
    scale_neuron_number,
    scale_synapse_number,
    scale_weights,
    external_compensation_current,
    recurrent_dc_from_network,
)

from human_microcircuit.reference_models.common.network import (
    indegree_matrix,
    full_mean_rates,
    external_indegrees,
    external_psc_weights,
    mean_psc_matrix,
    tau_syn_ex,
    psp_to_psc_network,
)


class ParameterBuilder:
    """
    Build a derived NetworkConfig.
    """

    def __init__(
        self,
        network_config: NetworkConfig,
    ) -> None:
        self._network_config = network_config

    def build(self) -> NetworkConfig:
        """
        Build a derived NetworkConfig.

        The returned object is independent from the original one.
        """

        network = self._network_config.model_copy(deep=True)

        network = self._apply_n_scaling(network)

        network = self._apply_k_scaling(network)

        network = psp_to_psc_network(network)

        network = scale_weights(network)

        network = self._apply_input_compensation(network)

        network = self._apply_external_poisson_rates(network)

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

            populations[name] = population.model_copy(
                update={
                    "size": scale_neuron_number(
                        population.size,
                        scaling.N_scaling,
                    )
                }
            )

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

        #
        # populations
        #

        populations = {}

        for name, population in network.populations.items():

            populations[name] = population.model_copy(
                update={
                    "background_indegree": (
                        population.background_indegree * scaling.K_scaling
                    )
                }
            )

        #
        # connections
        #

        connections = []

        for connection in network.connections:

            connections.append(
                connection.model_copy(
                    update={
                        "n_synapses": scale_synapse_number(
                            connection.n_synapses,
                            scaling.K_scaling,
                        )
                    }
                )
            )

        return network.model_copy(
            update={
                "populations": populations,
                "connections": connections,
            }
        )

    def _apply_external_poisson_rates(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        """
        Convert biological background rates into effective
        Poisson generator rates.

        PD14:

            effective_rate = bg_rate * K_ext
        """

        inputs = {}

        for pop_name, input_cfg in network.inputs.items():

            K_ext = network.populations[pop_name].background_indegree

            inputs[pop_name] = input_cfg.model_copy(
                update={
                    "rate": input_cfg.rate * K_ext,
                }
            )

        return network.model_copy(
            update={
                "inputs": inputs,
            }
        )

    def _apply_input_compensation(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        """
        Apply constant currrent compensation to account for the change in mean synaptic
        input due to synapse scaling.
        """

        # Original network quantities
        original = self._network_config

        if original.reference is None:
            return network

        scaling = original.scaling

        # Connection indegrees for recurrent and external connections
        indegrees = indegree_matrix(original)
        K_ext = external_indegrees(original)

        # Mean PSC amplitudes (pA) for recurrent and external connections
        PSC_ext = external_psc_weights(original)
        PSC_matrix = mean_psc_matrix(original)

        # Mean firing rates (Hz) of reference network populations
        mean_rates = full_mean_rates(original)

        # Synaptic time constant (ms) for excitatory synapses
        # (used for both recurrent and external contributions)
        tau_syn = tau_syn_ex(original)

        # Compute recurrent contribution to DC compensation from biological network quantities
        network_input = network_mean_input(
            mean_PSC_matrix=PSC_matrix,
            indegree_matrix=indegrees,
            mean_rates=mean_rates,
        )

        network_current = network_compensation_current(
            network_input=network_input,
            tau_syn=tau_syn,
            K_scaling=scaling.K_scaling,
        )

        # Compute external contribution to DC compensation from biological network quantities
        pop_names = list(original.populations.keys())
        bg_rates = np.asarray(
            [original.inputs[name].rate for name in pop_names],
            dtype=float,
        )
        external_current = external_compensation_current(
            PSC_ext=PSC_ext,
            K_ext=K_ext,
            bg_rate=bg_rates,
            tau_syn=tau_syn,
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
                        + external_current[i]
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
