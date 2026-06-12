"""
This module contains the implementation of the PD14 reference_models strategy,
which converts biological PSP amplitudes into PSC amplitudes.
"""

from human_microcircuit.config.network import NetworkConfig
from human_microcircuit.reference_models.common.synapses import (
    psp_to_psc as psp_amplitude_to_current,
)

def psp_to_psc_network(
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
                "mean": psp_amplitude_to_current(
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
                "mean": psp_amplitude_to_current(
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
