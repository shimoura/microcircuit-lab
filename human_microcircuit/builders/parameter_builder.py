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
        Build a derived configuration.

        Transformation order:

            1. N scaling

        Additional transformations (K scaling, DC compensation, etc.)
        will be added incrementally.
        """

        network = self._apply_n_scaling(self._network_config)

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
