"""
Parameter derivation.

This module derives simulator-ready parameters from the biological
network description while preserving the original immutable
configuration.
"""

from __future__ import annotations

from human_microcircuit.config.network import (
    NetworkConfig,
)

from human_microcircuit.physiology.scaling import (
    scale_neuron_number,
    scale_synapse_number,
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

        #
        # For now we simply return a copy.
        #
        # Future transformations:
        #
        # - neuron scaling
        # - synapse scaling
        # - weight scaling
        # - DC compensation
        #

        return self._network_config.model_copy(deep=True)

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
