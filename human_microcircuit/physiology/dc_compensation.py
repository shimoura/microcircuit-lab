"""
Functions for computing DC compensation currents.
"""

from __future__ import annotations


def dc_input_compensation(
    delta_weight: float,
    rate: float,
    indegree: float,
    tau_syn: float,
) -> float:
    """
    Compute the DC current compensating a synaptic weight change.

    Parameters
    ----------
    delta_weight
        Difference between the new and old PSC amplitudes (pA).

    rate
        External Poisson rate per synapse (Hz).

    indegree
        External indegree.

    tau_syn
        Synaptic time constant (ms).

    Returns
    -------
    float
        DC current in pA.
    """

    return (
        delta_weight
        * rate
        * indegree
        * tau_syn
        * 1e-3
    )