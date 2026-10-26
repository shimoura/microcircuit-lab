"""
Conversion between a PSP amplitude (mV) and the current (pA) that produces it,
for a builder whose weights are given as PSPs.
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
    This is the standard PSP-to-PSC conversion for a leaky
    integrate-and-fire neuron with a current-based synapse whose
    postsynaptic current decays as a single exponential (Rotter and
    Diesmann 1999). It only depends on the subthreshold membrane
    equation and the synaptic current kernel, so it holds for any
    neuron model with that dynamics, not one specific implementation.
    Potjans and Diesmann (2014) use it for their iaf_psc_exp
    populations, which is where it's most commonly seen in this field.
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
    Convert a PSP amplitude (mV) to the current amplitude (pA) that produces it.

    Holds for a current-based LIF neuron with exponential synaptic currents.
    It is named after NEST's ``iaf_psc_exp``, where people know it from, but it
    only depends on ``C_m``, ``tau_m`` and ``tau_syn`` (see
    :func:`psc_over_psp`), whatever the model is called.

    Parameters
    ----------
    psp
        The PSP amplitude, in mV.
    C_m
        Membrane capacitance, in pF.
    tau_m
        Membrane time constant, in ms.
    tau_syn
        Synaptic time constant, in ms.

    Returns
    -------
    float
        The current amplitude, in pA.
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
    Convert a current amplitude (pA) to the PSP amplitude (mV) it produces; the
    inverse of :func:`psp_to_psc_iaf_psc_exp`.

    Parameters
    ----------
    psc
        The current amplitude, in pA.
    C_m, tau_m, tau_syn
        As in :func:`psp_to_psc_iaf_psc_exp`.

    Returns
    -------
    float
        The PSP amplitude, in mV.
    """

    return psc / psc_over_psp(
        C_m=C_m,
        tau_m=tau_m,
        tau_syn=tau_syn,
    )
