"""
This module contains the implementation of the PD14 physiology strategy,
which converts biological PSP amplitudes into PSC amplitudes.
"""

from human_microcircuit.config.network import NetworkConfig
from human_microcircuit.physiology.synaptic_parameters import psp_to_psc


def apply_psp_to_psc(
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
