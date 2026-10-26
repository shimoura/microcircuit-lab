"""What ``poisson_background.yaml`` may contain: the background Poisson input of each population."""

from __future__ import annotations

from pydantic import Field, model_validator

from microcircuit_lab.config.connectivity import DelayDistribution, WeightDistribution
from microcircuit_lab.config.frozen_config import FrozenConfig


class PoissonBackgroundConfig(FrozenConfig):
    """
    Background Poisson input to a population: each neuron gets ``indegree``
    independent Poisson synapses, each firing at ``rate``.

    Scaling changes this input and compensates for it (see
    ``builder_tools/scaling.py`` and ``builder_tools/constant_current.py``). A
    ``StimulusConfig`` is for an input applied to some populations during
    part of the run.
    """

    rate: float = Field(
        ge=0.0, examples=[8.0], description="firing rate of each Poisson synapse (spikes/s)"
    )
    indegree: float = Field(
        ge=0.0, examples=[1600], description="Poisson synapses per neuron"
    )
    weight: WeightDistribution = Field(description="weight of each Poisson synapse")
    delay: DelayDistribution = Field(description="delay of each Poisson synapse")
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
        "indegree and synapse (a generator connects through one synapse model). "
        "Omit for a generator of its own",
    )

    @property
    def generator_rate(self) -> float:
        """Rate of the one Poisson generator that stands for the ``indegree`` synapses of each neuron (spikes/s)."""
        return self.rate * self.indegree


class PoissonBackgroundFile(FrozenConfig):
    """``poisson_background.yaml``: one entry per population name.

    Each value is a :class:`PoissonBackgroundConfig`: a ``rate`` and an
    ``indegree`` of at least 0, and a ``weight`` and ``delay`` written as in
    ``connectivity.yaml``.
    """

    poisson_background: dict[str, PoissonBackgroundConfig] = Field(
        description="one entry per population, keyed by its name; a population left out gets none",
    )

    @model_validator(mode="before")
    @classmethod
    def _refuse_old_forms(cls, data):
        if isinstance(data, dict) and "background_inputs" in data:
            raise ValueError(
                "background_inputs was renamed: the top-level key of this file is now "
                "poisson_background (poisson_background.yaml, and the manifest key in network.yaml)"
            )
        if isinstance(data, dict) and "background_mode" in data:
            raise ValueError(
                "background_mode was removed: the files show what runs. To replace the background "
                "by its mean current, write the network with replace_background_by_mean_current "
                "(microcircuit_lab.builder_tools), e.g. the pd14 builder's --background "
                "mean_current, and remove background_mode from this file"
            )
        return data
