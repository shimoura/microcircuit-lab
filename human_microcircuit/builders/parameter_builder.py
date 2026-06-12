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

from human_microcircuit.physiology.scaling import (
    scale_neuron_number,
    scale_synapse_number,
    scale_synaptic_weight,
)
from human_microcircuit.physiology.synaptic_parameters import (
    psp_to_psc,
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

        network = self._apply_psp_to_psc(network)

        network = self._apply_weight_scaling(network)

        network = self._apply_dc_compensation(network)

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

    def _apply_psp_to_psc(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        """
        Convert biological PSP amplitudes into PSC amplitudes.
        """

        #
        # recurrent connections
        #

        connections = []

        for connection in network.connections:

            target = network.populations[connection.target]

            tau_syn = target.neuron.parameters.tau_syn_ex

            weight = connection.weight.model_copy(
                update={
                    "mean": psp_to_psc(
                        psp=connection.weight.mean,
                        C_m=target.neuron.parameters.C_m,
                        tau_m=target.neuron.parameters.tau_m,
                        tau_syn=tau_syn,
                    )
                }
            )

            connections.append(
                connection.model_copy(
                    update={
                        "weight": weight,
                    }
                )
            )

        #
        # external inputs
        #

        inputs = {}

        for pop_name, input_cfg in network.inputs.items():

            target = network.populations[pop_name]

            tau_syn = target.neuron.parameters.tau_syn_ex

            weight = input_cfg.weight.model_copy(
                update={
                    "mean": psp_to_psc(
                        psp=input_cfg.weight.mean,
                        C_m=target.neuron.parameters.C_m,
                        tau_m=target.neuron.parameters.tau_m,
                        tau_syn=tau_syn,
                    )
                }
            )

            inputs[pop_name] = input_cfg.model_copy(
                update={
                    "weight": weight,
                }
            )

        return network.model_copy(
            update={
                "connections": connections,
                "inputs": inputs,
            }
        )

    def _apply_weight_scaling(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        """
        Apply square root synaptic weight scaling.

        w -> w / sqrt(K_scaling)
        """

        scaling = network.scaling

        #
        # recurrent
        #

        connections = []

        for connection in network.connections:

            weight = connection.weight.model_copy(
                update={
                    "mean": scale_synaptic_weight(
                        connection.weight.mean,
                        scaling.K_scaling,
                    )
                }
            )

            connections.append(
                connection.model_copy(
                    update={
                        "weight": weight,
                    }
                )
            )

        #
        # external
        #

        inputs = {}

        for pop_name, input_cfg in network.inputs.items():

            weight = input_cfg.weight.model_copy(
                update={
                    "mean": scale_synaptic_weight(
                        input_cfg.weight.mean,
                        scaling.K_scaling,
                    )
                }
            )

            inputs[pop_name] = input_cfg.model_copy(
                update={
                    "weight": weight,
                }
            )

        return network.model_copy(
            update={
                "connections": connections,
                "inputs": inputs,
            }
        )