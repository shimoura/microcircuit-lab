"""What ``neurons.yaml`` may contain: one entry per neuron model, by name.

A population names its neuron (``neuron: excitatory``); the neuron entry holds
the simulator's model name and its parameters.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from microcircuit_lab.config.base import FrozenConfig


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

    `I_e` (constant input current, pA) is the one field this package reads
    back directly, since DC-compensation (see network/prepare.py)
    adds to it when scaling the network. It's declared explicitly here and
    defaults to 0.0, since a constant input current at zero is the common
    starting point across point-neuron models generally.

    Values must be numeric; anything else (a string, a list, ...) is
    rejected here rather than surfacing as a confusing simulator-side
    error.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    I_e: float = 0.0

    @model_validator(mode="after")
    def _check_extra_params_are_numeric(self) -> "NeuronParams":
        non_numeric = {
            key: value
            for key, value in (self.__pydantic_extra__ or {}).items()
            if not isinstance(value, (int, float))
        }
        if non_numeric:
            raise ValueError(
                f"Neuron parameters must be numeric, got non-numeric values: {non_numeric!r}."
            )
        return self

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
        return {name: values[name] for name in names}


class NeuronEntry(FrozenConfig):
    """One entry of ``neurons.yaml`` (the file key is the neuron's name)."""

    model: str = Field(
        description="the simulator's neuron model name, e.g. iaf_psc_exp"
    )
    parameters: NeuronParams = Field(
        description="parameters passed to that model as-is; keys are "
        "model-specific and the backend validates them (I_e defaults to 0.0)"
    )
    psp_conversion_aliases: dict[str, str] = Field(
        default_factory=dict,
        description="only for `unit: PSP` connections whose neuron names "
        "C_m/tau_m/tau_syn_ex/tau_syn_in differently, e.g. {C_m: cm}",
    )


class NeuronsFile(FrozenConfig):
    """``neurons.yaml``."""

    neurons: dict[str, NeuronEntry]


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
