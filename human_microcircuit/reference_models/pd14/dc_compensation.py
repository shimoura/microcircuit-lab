"""
This module contains the implementation of the DC compensation strategy
specific to the Potjans & Diesmann (2014) microcircuit model.
"""

import numpy as np


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


def external_dc_compensation(
    PSC_ext: np.ndarray,
    K_ext: np.ndarray,
    bg_rate: np.ndarray,
    tau_syn: np.ndarray,
    K_scaling: float,
) -> np.ndarray:
    """
    Compute the external DC compensation term from PD14.
    """

    return 0.001 * tau_syn * (1.0 - np.sqrt(K_scaling)) * PSC_ext * K_ext * bg_rate


def recurrent_dc_from_network(
    mean_PSC_matrix: np.ndarray,
    indegree_matrix: np.ndarray,
    mean_rates: np.ndarray,
    tau_syn: np.ndarray,
    K_scaling: float,
) -> np.ndarray:
    """
    Compute the recurrent DC compensation from biological network
    quantities.
    """

    input_rec = recurrent_mean_input(
        mean_PSC_matrix=mean_PSC_matrix,
        indegree_matrix=indegree_matrix,
        mean_rates=mean_rates,
    )

    return recurrent_dc_compensation(
        input_rec=input_rec,
        tau_syn=tau_syn,
        K_scaling=K_scaling,
    )
