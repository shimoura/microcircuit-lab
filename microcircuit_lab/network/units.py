"""
Utilities related to synaptic parameters and transformations.

This module provides operations on individual synapses, independent
of the network topology or a particular reference model.

Typical examples include conversions between postsynaptic potentials
(PSPs) and postsynaptic currents (PSCs), as well as other synapse-level
transformations and parameter conversions.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from microcircuit_lab.config.neurons import NeuronParams


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


def convert_psp_to_psc(
    model: str,
    psp: float,
    params: NeuronParams,
    *,
    aliases: Mapping[str, str] | None = None,
) -> float:
    """
    Convert a PSP amplitude (mV) to a current (pA) with a neuron's parameters.

    Used for ``unit: PSP`` weights. It needs ``C_m``, ``tau_m``, ``tau_syn_ex``
    and ``tau_syn_in``, under those names or under the names given in
    ``aliases`` (a neuron's ``psp_conversion_aliases``, e.g. for a NESTML
    model). The code can't check the neuron's dynamics: a model that has these
    four parameters but is not a current-based LIF neuron with exponential
    synaptic currents gets a wrong weight without an error.

    Parameters
    ----------
    model
        The neuron model's name (only used in error messages).
    psp
        The PSP amplitude, in mV; a negative one uses ``tau_syn_in``.
    params
        The neuron's parameters.
    aliases
        ``{canonical name: the model's name}`` for parameters named differently.

    Returns
    -------
    float
        The current amplitude, in pA.

    Raises
    ------
    ValueError
        Naming the missing parameter, if one of the four is missing.
    """

    aliases = aliases or {}
    canonical_names = ("C_m", "tau_m", "tau_syn_ex", "tau_syn_in")
    lookup_names = [aliases.get(name, name) for name in canonical_names]

    try:
        raw = params.require(*lookup_names)
    except KeyError as exc:
        raise ValueError(
            f"neuron model {model!r}: {exc.args[0]} unit: PSP requires a "
            "current-based LIF neuron with single-exponential synaptic "
            "currents, exposing C_m, tau_m, tau_syn_ex and tau_syn_in "
            "(directly, or via a psp_conversion_aliases entry on its "
            "NeuronConfig if it names them differently). Give this "
            "weight unit: PSC (already a current amplitude in pA) or "
            "unit: native (used exactly as given, e.g. for a "
            "conductance-based model) instead."
        ) from exc

    values = dict(zip(canonical_names, (raw[name] for name in lookup_names)))
    tau_syn = values["tau_syn_ex"] if psp >= 0 else values["tau_syn_in"]

    return psp_to_psc_iaf_psc_exp(
        psp=psp,
        C_m=values["C_m"],
        tau_m=values["tau_m"],
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
