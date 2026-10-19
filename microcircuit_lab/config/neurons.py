"""What ``neurons.yaml`` may contain: one entry per neuron model, by name.

A population names its neuron (``neuron: excitatory``); the neuron entry holds
the simulator's model name and its parameters.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt

from microcircuit_lab.config.distributions import PerNeuronValue
from microcircuit_lab.config.frozen_config import FrozenConfig


class NeuronParams(BaseModel):
    """
    Parameters of a neuron model, passed to the simulator as given.

    The keys are not fixed, because neuron models differ in the parameters they
    accept. The simulator raises an error for a name it does not know.

    A parameter can differ from neuron to neuron: write a distribution instead
    of a number (see ``config/distributions.py``), for example
    ``V_th: {distribution: uniform, min: -52, max: -48}``.

    ``I_e`` (constant input current, pA) is the one parameter read back here,
    because scaling adds a compensation current to it (see
    ``network/compensation.py``). It defaults to 0.0 and is always a number.

    Values must be numbers, lists of numbers (one entry per receptor port, for
    example ``tau_syn: [0.5, 5.0]``) or distributions. Anything else is rejected
    here instead of causing a confusing error in the simulator.
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
        Return the named parameters, or raise an error if any is missing or
        drawn per neuron.

        Code that needs specific parameters (the PSP-to-PSC conversion, for
        example) uses this to check that they are present.
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
    A neuron model: its name, the simulator's model name and its parameters.

    ``psp_conversion_aliases`` matters only for connections with ``unit: PSP``.
    It maps a name the conversion needs (``C_m``, ``tau_m``, ``tau_syn_ex``,
    ``tau_syn_in``) to what ``parameters`` calls it, for a model that names them
    differently. If empty, ``parameters`` uses those names. See
    ``network.psp_psc_conversion.convert_psp_to_psc``.
    """

    name: str
    model: str
    parameters: NeuronParams
    psp_conversion_aliases: dict[str, str] = Field(default_factory=dict)
