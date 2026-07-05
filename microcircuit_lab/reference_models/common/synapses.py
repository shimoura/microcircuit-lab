"""
Utilities related to synaptic parameters and transformations.

This module provides operations on individual synapses, independent
of the network topology or a particular reference model.

Typical examples include conversions between postsynaptic potentials
(PSPs) and postsynaptic currents (PSCs), as well as other synapse-level
transformations and parameter conversions.
"""

from __future__ import annotations

import numpy as np


def psc_over_psp(
    C_m: float,
    tau_m: float,
    tau_syn: float,
) -> float:
    """
    Compute the conversion factor PSC / PSP.

    Parameters
    ----------
    C_m
        Membrane capacitance (pF).

    tau_m
        Membrane time constant (ms).

    tau_syn
        Synaptic time constant (ms).

    Returns
    -------
    float
        Factor converting PSP (mV) to PSC (pA).

    Notes
    -----
    Mathematical formulation follows the Potjans-Diesmann
    microcircuit implementation.
    """

    if np.isclose(tau_syn, tau_m):
        raise ValueError("tau_syn and tau_m must be different.")

    eps = tau_syn / tau_m

    return C_m * eps ** (-1.0 / (1.0 - eps)) / tau_m


def psp_to_psc_iaf_psc_exp(
    psp: float,
    C_m: float,
    tau_m: float,
    tau_syn: float,
) -> float:
    """
    Convert a PSP amplitude to the equivalent PSC amplitude for
    current-based LIF neurons with exponential synaptic currents
    (iaf_psc_exp).
    """

    return psp * psc_over_psp(
        C_m=C_m,
        tau_m=tau_m,
        tau_syn=tau_syn,
    )


def psc_to_psp(
    psc: float,
    C_m: float,
    tau_m: float,
    tau_syn: float,
) -> float:
    """
    Convert a PSC amplitude (pA) to a PSP amplitude (mV).
    """

    return psc / psc_over_psp(
        C_m=C_m,
        tau_m=tau_m,
        tau_syn=tau_syn,
    )
