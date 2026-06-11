"""
Mathematical functions reproducing the Potjans & Diesmann (2014)
microcircuit parameter derivation.

This module intentionally contains only pure functions.

No NEST code.
No Pydantic.
No file I/O.
No side effects.

Its purpose is to provide a mathematically validated reference
implementation that can later be used by ParameterBuilder.
"""

from __future__ import annotations

import numpy as np


def num_synapses_from_conn_prob(
    conn_prob: float,
    n_source: int,
    n_target: int,
) -> int:
    """
    Compute the total number of synapses from a connection probability.

    Parameters
    ----------
    conn_prob
        Connection probability.

    n_source
        Number of source neurons.

    n_target
        Number of target neurons.

    Returns
    -------
    int
        Expected total number of synapses.
    """

    if conn_prob <= 0.0:
        return 0

    prod = n_source * n_target

    num_syn = np.log(1.0 - conn_prob) / np.log((prod - 1.0) / prod)

    return int(round(num_syn))


def dc_input_compensating_poisson(
    bg_rate: float,
    K_ext: np.ndarray,
    tau_syn: float,
    PSC_ext: float,
) -> np.ndarray:
    """
    Compute the DC input that compensates for replacing Poisson
    background input.

    Parameters
    ----------
    bg_rate
        External Poisson firing rate (spikes/s).

    K_ext
        External indegree for each population.

    tau_syn
        Synaptic time constant (ms).

    PSC_ext
        External synaptic weight (pA).

    Returns
    -------
    np.ndarray
        DC input (pA) for each population.
    """

    return bg_rate * K_ext * PSC_ext * tau_syn * 0.001


def adjust_weights_and_input_to_synapse_scaling(
    PSC_matrix_mean,
    PSC_ext,
    K_scaling,
    mean_PSC_matrix,
    mean_PSC_ext,
    DC_amp,
    poisson_input,
    bg_rate,
    K_ext,
    tau_syn,
):
    """
    Reproduce the PD14 adjustment for synapse scaling.

    This function intentionally mirrors the mathematics of the
    original implementation and should remain free of simulator
    dependencies.
    """

    PSC_matrix_new = PSC_matrix_mean / np.sqrt(K_scaling)

    PSC_ext_new = PSC_ext / np.sqrt(K_scaling)

    if poisson_input:

        input_rec = np.sum(mean_PSC_matrix, axis=1)

        input_ext = mean_PSC_ext

        DC_amp_new = DC_amp + 0.001 * tau_syn * (1.0 - np.sqrt(K_scaling)) * (
            input_rec + input_ext
        )

    else:

        DC_amp_new = DC_amp

    return (
        PSC_matrix_new,
        PSC_ext_new,
        DC_amp_new,
    )