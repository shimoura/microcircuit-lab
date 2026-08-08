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

from microcircuit_lab.config.network import NeuronParams


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
    Convert a PSP amplitude to the equivalent PSC amplitude for a
    current-based LIF neuron with single-exponential synaptic currents.

    Named after NEST's iaf_psc_exp, the model most people recognize this
    from, but the formula (see psc_over_psp) only depends on C_m, tau_m
    and tau_syn, so it applies to any neuron with that dynamics
    regardless of what it's called or which simulator it runs on.
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
    Convert a PSP amplitude (mV) to a PSC amplitude (pA) for a population
    using neuron model `model` with parameters `params`.

    Applies whenever `params` has C_m, tau_m, tau_syn_ex and tau_syn_in
    (read under those names, or under `aliases[name]` for any of the
    four `aliases` remaps), which is what the conversion needs and, in
    practice, what a current-based LIF neuron with single-exponential
    synaptic currents looks like: a conductance-based model exposes its
    leak as g_L instead of a fixed tau_m, so it won't have all four
    under any naming. `aliases` is how a model whose own parameters use
    a different naming convention (e.g. a NESTML model) than NEST's
    iaf_psc_exp still gets to use this conversion, see NeuronConfig's
    psp_conversion_aliases.

    This module doesn't know about `model` as a simulator identifier,
    so unlike `unit: PSC`/`unit: native` it can't be told explicitly
    not to apply; giving unit: PSP to a population whose neuron doesn't
    actually have this dynamics, even if it happens to expose these
    four names (aliased or not), will silently produce the wrong
    weight, so that choice is on whoever wrote the config.

    Raises ValueError, naming the missing parameter, if `params` is
    missing one of the four.
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
    Convert a PSC amplitude (pA) to a PSP amplitude (mV).
    """

    return psc / psc_over_psp(
        C_m=C_m,
        tau_m=tau_m,
        tau_syn=tau_syn,
    )
