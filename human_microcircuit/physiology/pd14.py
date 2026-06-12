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
    PSC_matrix_mean
        Matrix of mean PSC amplitudes (pA).
    PSC_ext
        External synaptic weight (pA).
    K_scaling
        Indegree scaling factor.
    mean_PSC_matrix
        Matrix of mean PSC amplitudes (pA) before scaling.
    mean_PSC_ext
        External synaptic weight (pA) before scaling.
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
            DC_amp_new
            + 0.001
            * tau_syn
            * (1.0 - np.sqrt(K_scaling))
            * input_ext
        )

    return (
        PSC_matrix_new,
        PSC_ext_new,
        DC_amp_new,
    )


def recurrent_mean_input(
    mean_PSC_matrix: np.ndarray,
    indegree_matrix: np.ndarray,
    mean_rates: np.ndarray,
) -> np.ndarray:
    """
    Compute the recurrent mean synaptic input used in the
    Potjans & Diesmann (2014) scaling equations.

    Parameters
    ----------
    mean_PSC_matrix
        Matrix of mean PSC amplitudes (pA).

    indegree_matrix
        Matrix of indegrees.

    mean_rates
        Mean firing rate of each source population (Hz).

    Returns
    -------
    np.ndarray
        Mean recurrent input for each target population.
    """

    return np.sum(
        mean_PSC_matrix * indegree_matrix * mean_rates,
        axis=1,
    )


def recurrent_dc_compensation(
    input_rec: np.ndarray,
    tau_syn: float,
    K_scaling: float,
) -> np.ndarray:
    """
    Compute the recurrent DC compensation term from
    Potjans & Diesmann (2014).

    Parameters
    ----------
    input_rec
        Mean recurrent synaptic input.

    tau_syn
        Synaptic time constant (ms).

    K_scaling
        Indegree scaling factor.

    Returns
    -------
    np.ndarray
        DC compensation current.
    """

    return 0.001 * tau_syn * (1.0 - np.sqrt(K_scaling)) * input_rec


def indegree_from_synapses(
    n_synapses: float,
    target_population_size: float,
) -> float:
    """
    Compute indegree from total number of synapses.
    """

    return n_synapses / target_population_size