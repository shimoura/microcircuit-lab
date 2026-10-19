"""What ``populations.yaml`` may contain: one row per population.

``PopulationEntry`` is a row as written in the file (the neuron given by name);
``PopulationConfig`` is the same population once the network is read, with
its neuron entry filled in.
"""

from __future__ import annotations

from pydantic import Field

from microcircuit_lab.config.base import FrozenConfig
from microcircuit_lab.config.distributions import PerNeuronValue
from microcircuit_lab.config.neurons import NeuronConfig


class PopulationEntry(FrozenConfig):
    """One row of ``populations.yaml``."""

    name: str = Field(
        examples=["L23_E"],
        description="unique population name; referenced by connectivity, "
        "background_inputs, stimuli and reference",
    )
    size: int = Field(gt=0, examples=[20683], description="number of neurons")
    neuron: str = Field(
        examples=["excitatory"],
        description="name of an entry in neurons.yaml; every neuron of the population "
        "gets that model and those parameters",
    )
    initial_state: dict[str, PerNeuronValue] = Field(
        default_factory=dict,
        examples=[{"V_m": {"distribution": "normal", "mean": -58.0, "std": 10.0}}],
        description="starting value of each state variable of the neuron model, e.g. V_m (mV): "
        "a number, or a distribution drawn per neuron: its name and its arguments, e.g. "
        "{distribution: normal, mean: -58, std: 10} (for NEST, any function in nest.random); "
        "a variable left out starts at the model's default",
    )
    background_indegree: float = Field(
        default=0.0,
        ge=0.0,
        examples=[2510.0],
        description="background-input connections per neuron; multiplies the "
        "rate in background_inputs.yaml",
    )


class PopulationsFile(FrozenConfig):
    """``populations.yaml``."""

    populations: list[PopulationEntry] = Field(description="one entry per population")


class PopulationConfig(FrozenConfig):
    """Description of one neuronal population."""

    name: str
    size: int = Field(gt=0)

    neuron: NeuronConfig

    initial_state: dict[str, PerNeuronValue] = Field(default_factory=dict)
    background_indegree: float = Field(default=0.0, ge=0.0)
