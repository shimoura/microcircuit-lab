"""
Unit conversions for single synapses, such as post-synaptic potentials (PSPs)
to post-synaptic currents (PSCs).
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.config.neurons import NeuronParams
from microcircuit_lab.config.populations import PopulationConfig
from microcircuit_lab.config.stimuli import DcStimulusConfig


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


def convert_psp_weight(population: PopulationConfig, psp: float) -> float:
    """
    Convert one PSP-unit weight (mV) to PSC (pA) for `population`.

    Any error from convert_psp_to_psc() is re-raised with the population
    name added, so a failure points at which population caused it.
    """

    try:
        return convert_psp_to_psc(
            population.neuron.model,
            psp,
            population.neuron.parameters,
            aliases=population.neuron.psp_conversion_aliases,
        )
    except ValueError as exc:
        raise ValueError(f"Population {population.name!r}: {exc}") from exc


def convert_psp_weights(network: NetworkConfig, psp: np.ndarray) -> np.ndarray:
    """All connection weights, those of the rows marked ``psp`` converted
    from mV to pA (the others as they are).

    The conversion is linear in the PSP and its sign picks ``tau_syn_ex`` or
    ``tau_syn_in``, so it is one factor per target population and sign,
    computed only for the populations that need it.
    """

    names = list(network.populations)
    target = network.connections.population_index("target", names)
    mean = network.connections["weight.mean"].astype(float)
    converted = mean.copy()
    for sign in (1.0, -1.0):
        rows = psp & (np.sign(mean) == sign)
        factor = np.zeros(len(names))
        for i in np.unique(target[rows]):
            factor[i] = sign * convert_psp_weight(network.populations[names[i]], sign)
        converted[rows] = mean[rows] * factor[target[rows]]
    return converted


def convert_network_psp_to_psc(network: NetworkConfig) -> NetworkConfig:
    """
    Convert synaptic weights stored as PSP amplitudes (``unit: PSP``) into
    PSC amplitudes. Any other unit (``PSC``, ``native``, ...) is left
    untouched; it is not reinterpreted as PSP.

    The conversion is performed independently for each target population
    using its neuron parameters, via :func:`convert_psp_to_psc`;
    see that function for what it requires. A population whose neuron
    parameters don't support it raises ValueError; give its connections
    ``unit: native`` (or ``PSC`` if the weights are genuinely already
    current amplitudes in pA) instead.
    """

    connections = network.connections
    psp = connections["weight.unit"] == "PSP"
    if psp.any():
        connections = connections.with_columns(copy=False, **{
            "weight.mean": convert_psp_weights(network, psp),
            "weight.unit": np.where(psp, "PSC", connections["weight.unit"]),
        })

    background_inputs = {}
    for pop_name, input_cfg in network.background_inputs.items():
        if input_cfg.weight.unit != "PSP":
            background_inputs[pop_name] = input_cfg
            continue

        target = network.populations[pop_name]
        mean = convert_psp_weight(target, input_cfg.weight.mean)
        weight = input_cfg.weight.model_copy(update={"mean": mean, "unit": "PSC"})
        background_inputs[pop_name] = input_cfg.model_copy(update={"weight": weight})

    stimuli = []
    for stimulus in network.stimuli:
        if isinstance(stimulus, DcStimulusConfig) or stimulus.weight.unit != "PSP":
            stimuli.append(stimulus)
            continue

        # A stimulus has one weight shared across all its targets, so a PSP
        # amplitude only maps onto a single PSC amplitude if every target
        # converts it the same way. This is checked by converting for each
        # target and comparing the results, rather than by comparing which
        # neuron parameters happen to be involved.
        converted = {
            convert_psp_weight(network.populations[t], stimulus.weight.mean)
            for t in stimulus.targets
        }
        if len(converted) > 1:
            raise ValueError(
                f"Cannot convert a unit: PSP stimulus weight shared across "
                f"targets {stimulus.targets!r}: those populations don't "
                "convert it to the same PSC amplitude. Split into separate "
                "stimuli (one per distinct neuron type), or give the weight "
                "as unit: PSC/native instead."
            )

        weight = stimulus.weight.model_copy(update={"mean": converted.pop(), "unit": "PSC"})
        stimuli.append(stimulus.model_copy(update={"weight": weight}))

    return network.model_copy(
        update={"connections": connections, "background_inputs": background_inputs, "stimuli": stimuli}
    )
