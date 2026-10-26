"""What ``background_inputs.yaml`` may contain: the always-on input of each population."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from microcircuit_lab.config.connectivity import DelayDistribution, WeightDistribution
from microcircuit_lab.config.frozen_config import FrozenConfig


class BackgroundInputConfig(FrozenConfig):
    """
    Always-on Poisson input to a population.

    Scaling changes this input and compensates for it (see
    ``builder_tools/scaling.py`` and ``builder_tools/constant_current.py``). A
    ``StimulusConfig`` is for an input applied to some populations during
    part of the run.
    """

    rate: float = Field(
        ge=0.0, examples=[8.0], description="background Poisson rate per connection (spikes/s)"
    )
    weight: WeightDistribution = Field(description="weight of each background connection")
    delay: DelayDistribution = Field(description="delay of each background connection")
    synapse: str | None = Field(
        default=None,
        examples=["depressing"],
        description="name of an entry in synapses.yaml; omit for the default synapse",
    )
    generator: str | None = Field(
        default=None,
        examples=["L23_E"],
        description="a name for the population's Poisson generator: populations that give the "
        "same name share one generator, and each neuron still gets its own independent spike "
        "train. Saves memory when many populations have the same input, but "
        "gives other random draws than one generator each. They need the same rate, "
        "background_indegree and synapse (a generator connects through one synapse model). "
        "Omit for a generator of its own",
    )


class BackgroundInputsFile(FrozenConfig):
    """``background_inputs.yaml``: one entry per population name.

    Each value is a :class:`BackgroundInputConfig`: a ``rate`` of at least 0,
    and a ``weight`` and ``delay`` written as in ``connectivity.yaml``.
    """

    background_inputs: dict[str, BackgroundInputConfig] = Field(
        description="one entry per population, keyed by its name; a population left out gets none",
    )
    background_mode: Literal["poisson", "mean_current"] = Field(
        default="poisson",
        description="'mean_current' replaces each population's Poisson input by its mean, "
        "a constant current (Potjans & Diesmann 2014, Fig. 5); for a constant input of your "
        "own, use I_e in neurons.yaml or a dc stimulus",
    )
