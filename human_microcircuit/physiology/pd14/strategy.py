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
    psp_to_psc,
)


class PD14Strategy(PhysiologyStrategy):
    """
    Physiology strategy implementing the
    Potjans & Diesmann (2014) derivation.
    """

    def apply_psp_to_psc(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        """
        Convert biological PSP amplitudes into PSC amplitudes.
        """

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

    def apply_weight_scaling(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        return network

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
