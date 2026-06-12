"""
This module contains the implementation of the PD14 physiology strategy,
which includes scaling transformations specific to the Potjans & Diesmann (2014) model.
"""

import numpy as np

from human_microcircuit.config.network import NetworkConfig
from human_microcircuit.physiology.common.scaling import (
    scale_weight_sqrt,
)
from human_microcircuit.physiology.pd14.dc_compensation import (
    recurrent_mean_input,
    recurrent_dc_compensation,
)


def scale_weights(
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


def adjust_weights_and_input_to_synapse_scaling(
    mean_PSC_matrix,
    PSC_ext,
    K_scaling,
    DC_amp,
    bg_input_type,
    bg_rate,
    K_ext,
    tau_syn,
    indegree_matrix,
    full_mean_rates,
):
    """
    Adjust synaptic weights and DC compensation according to the
    Potjans & Diesmann (2014) synapse scaling procedure.

    Parameters
    ----------
    PSC_ext
        External synaptic weight (pA).
    K_scaling
        Indegree scaling factor.
    mean_PSC_matrix
        Matrix of mean PSC amplitudes (pA) before scaling.
    DC_amp
        DC compensation amplitude (pA) before scaling.
    poisson_input
        Whether Poisson input is used.
    bg_rate
        External Poisson firing rate (spikes/s).
    K_ext
        External indegree for each population.
    tau_syn
        Synaptic time constant (ms).
    indegree_matrix
        Matrix of indegrees for each connection.
    full_mean_rates
        Mean firing rates of all populations (Hz).

    Returns
    -------
    tuple
        Adjusted PSC matrices and DC amplitude.
    """
    # 1. Scale recurrent PSC
    PSC_matrix_new = mean_PSC_matrix / np.sqrt(K_scaling)

    # 2. Scale external PSC
    PSC_ext_new = PSC_ext / np.sqrt(K_scaling)

    # 3. Recurrent mean input
    input_rec = recurrent_mean_input(
        mean_PSC_matrix=mean_PSC_matrix,
        indegree_matrix=indegree_matrix,
        mean_rates=full_mean_rates,
    )

    # 4. Recurrent DC compensation
    DC_amp_new = DC_amp + recurrent_dc_compensation(
        input_rec=input_rec,
        tau_syn=tau_syn,
        K_scaling=K_scaling,
    )

    # 5. External compensation
    if bg_input_type == "poisson":

        input_ext = PSC_ext * K_ext * bg_rate

        DC_amp_new = (
            DC_amp_new + 0.001 * tau_syn * (1.0 - np.sqrt(K_scaling)) * input_ext
        )

    return (
        PSC_matrix_new,
        PSC_ext_new,
        DC_amp_new,
    )
