"""What ``neurons.yaml`` may contain: one entry per neuron model, by name.

A population names its neuron (``neuron: excitatory``); the neuron entry holds
the simulator's model name and its parameters.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt

from microcircuit_lab.config.base import FrozenConfig
from microcircuit_lab.config.distributions import PerNeuronValue


class NeuronParams(BaseModel):
    """
    Parameters for a neuron model, passed through to the simulator backend
    as-is.

    Deliberately open-ended rather than a fixed field list: neuron models
    differ in what they accept (a current-based integrate-and-fire model,
    a conductance-based one, an adaptive-exponential one, ...), so
    hard-coding one parameter set here would only ever fit a subset of
    them. Whatever keys you supply (besides `I_e`, see below) are set on
    the simulator-side neuron exactly as given. The simulator backend is
    the source of truth for which names a given model accepts, and it is
    the one that raises an error if given a name it doesn't recognize.
    This layer stays simulator-independent and does not duplicate that
    check.

    A parameter can also differ from neuron to neuron: write a distribution
    instead of a number (see config.distributions), e.g.
    ``V_th: {distribution: uniform, min: -52, max: -48}``.

    `I_e` (constant input current, pA) is the one field this package reads
    back directly, since DC-compensation (see network/prepare.py)
    adds to it when scaling the network. It's declared explicitly here and
    defaults to 0.0, since a constant input current at zero is the common
    starting point across point-neuron models generally. It is always a
    number.

    Values must be numbers, lists of numbers (a parameter with one entry per
    receptor port, e.g. ``tau_syn: [0.5, 5.0]``) or distributions; anything
    else (a string, ...) is rejected here rather than surfacing as a
    confusing simulator-side error.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    # A list is one value with several entries, the same for every neuron,
    # e.g. the time constant of each receptor port: tau_syn: [0.5, 5.0].
    __pydantic_extra__: dict[str, PerNeuronValue | list[StrictInt | StrictFloat]] = Field(
        init=False
    )

    I_e: float = Field(
        default=0.0,
        description="constant input current (pA) of every neuron, for the whole run; a scaled "
        "network adds its compensation current to it",
    )

    def require(self, *names: str) -> dict[str, float]:
        """
        Return the named parameters, or raise a clear error if any weren't
        provided.

        Parameters are open-ended here, so this is the only way for code
        that needs specific parameters by name (e.g. a PSP-to-PSC
        conversion formula tied to one neuron model) to know whether what
        it needs is actually present.
        """

        values = self.model_dump()
        missing = [name for name in names if name not in values]
        if missing:
            raise KeyError(f"Missing neuron parameters: {missing}.")
        drawn = [name for name in names if isinstance(values[name], dict)]
        if drawn:
            raise ValueError(
                f"Neuron parameters {drawn} are drawn per neuron; this needs one value "
                "for the whole population (e.g. the PSP-to-PSC conversion)."
            )
        return {name: values[name] for name in names}


class NeuronEntry(FrozenConfig):
    """One entry of ``neurons.yaml`` (the file key is the neuron's name)."""

    model: str = Field(
        examples=["iaf_psc_exp"],
        description="the simulator's neuron model name, e.g. iaf_psc_exp",
    )
    parameters: NeuronParams = Field(
        examples=[
            {"C_m": 250.0, "tau_m": 10.0, "tau_syn_ex": 0.5, "tau_syn_in": 0.5,
             "E_L": -65.0, "V_th": -50.0, "V_reset": -65.0, "t_ref": 2.0}
        ],
        description="parameters passed to that model as-is; keys are "
        "model-specific and the backend validates them (I_e defaults to 0.0); a value is a "
        "number, a list of numbers (e.g. tau_syn: [0.5, 5.0], one per receptor port), or a "
        "distribution drawn per neuron like in initial_state "
        "(I_e and the parameters a PSP weight is converted with must be numbers)"
    )
    psp_conversion_aliases: dict[str, str] = Field(
        default_factory=dict,
        description="only for `unit: PSP` connections whose neuron names "
        "C_m/tau_m/tau_syn_ex/tau_syn_in differently, e.g. {C_m: cm}",
    )


class NeuronsFile(FrozenConfig):
    """``neurons.yaml``."""

    neurons: dict[str, NeuronEntry] = Field(
        description="one entry per neuron, keyed by any name; populations refer to it by that name",
    )


class NeuronConfig(FrozenConfig):
    """
    Configuration for a neuron model.
    This is a pure data container for the parameters of a neuron model.

    psp_conversion_aliases:
        Only relevant to connections that use ``unit: PSP``. Maps a
        canonical name the conversion needs ("C_m", "tau_m",
        "tau_syn_ex", "tau_syn_in") to whatever `parameters` actually
        calls it, for a model that names them differently (e.g. a
        NESTML model with its own naming convention). Empty by default,
        meaning `parameters` already uses those names directly (NEST's
        iaf_psc_exp and its usual variants). See
        network.units.convert_psp_to_psc.
    """

    name: str
    model: str
    parameters: NeuronParams
    psp_conversion_aliases: dict[str, str] = Field(default_factory=dict)
