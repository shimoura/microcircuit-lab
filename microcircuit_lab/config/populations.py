"""What ``populations.yaml`` may contain: one row per population.

``PopulationEntry`` is a row as written in the file (the neuron given by name);
``PopulationConfig`` is the same population once the network is read, with
its neuron entry filled in.
"""

from __future__ import annotations

from pydantic import Field

from microcircuit_lab.config.base import FrozenConfig
from microcircuit_lab.config.neurons import NeuronConfig


class PopulationEntry(FrozenConfig):
    """One row of ``populations.yaml``."""

    name: str = Field(
        description="unique population name; referenced by connectivity, "
        "background_inputs, stimuli and reference"
    )
    size: int = Field(gt=0, description="number of neurons")
    neuron: str = Field(description="name of an entry in neurons.yaml")
    V0_mean: float = Field(description="mean initial membrane potential (mV)")
    V0_std: float = Field(
        ge=0.0, description="standard deviation of the initial potential (mV)"
    )
    background_indegree: float = Field(
        default=0.0,
        ge=0.0,
        description="background-input connections per neuron; multiplies the "
        "rate in background_inputs.yaml",
    )


class PopulationsFile(FrozenConfig):
    """``populations.yaml``."""

    populations: list[PopulationEntry]


class PopulationConfig(FrozenConfig):
    """Description of one neuronal population."""

    name: str
    size: int = Field(gt=0)

    neuron: NeuronConfig

    V0_mean: float
    V0_std: float = Field(ge=0.0)
    background_indegree: float = Field(default=0.0, ge=0.0)
