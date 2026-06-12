"""
PD14 physiology strategy.
"""

# NOTE:
# This strategy is intentionally introduced as a no-op.
# PD14-specific transformations will be migrated here
# incrementally without changing external behavior.

from __future__ import annotations

from human_microcircuit.config.network import (
    NetworkConfig,
)

from human_microcircuit.physiology.strategy import (
    PhysiologyStrategy,
)

from human_microcircuit.physiology.synaptic_parameters import (
    scale_weight_sqrt,
)

from human_microcircuit.physiology.pd14.psp import (
    psp_to_psc,
)


class PD14Strategy(PhysiologyStrategy):
    """
    Physiology strategy implementing the
    Potjans & Diesmann (2014) derivation.
    """

    def psp_to_psc(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        return psp_to_psc(network)

    def apply_weight_scaling(
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
                    "mean": scale_weight_sqrt(
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
                    "mean": scale_weight_sqrt(
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

    def apply_dc_compensation(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        return network

    def apply_external_poisson_rates(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        return network
