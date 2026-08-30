"""
Assemble a validated :class:`NetworkConfig` from a :class:`NetworkDirectory`.

The directory has already been schema-checked file by file (see
:mod:`microcircuit_lab.config.files`). What is left is resolving the
references *between* files -- a population names its neuron, a connection
names its populations -- and handing back the immutable
:class:`NetworkConfig` the rest of the framework consumes.

No numerical parameter derivation happens here (that is
:class:`~microcircuit_lab.network.preprocessing.NetworkPreprocessor`), and
no simulator-specific code belongs here.
"""

from __future__ import annotations

from microcircuit_lab.config.files import NetworkDirectory
from microcircuit_lab.config.network import (
    BackgroundInputConfig,
    ConnectionConfig,
    NetworkConfig,
    NeuronConfig,
    PopulationConfig,
)


class NetworkConfigLoader:
    """Resolve cross-file references and build the immutable NetworkConfig."""

    def __init__(self, directory: NetworkDirectory) -> None:
        self._directory = directory

    def build(self) -> NetworkConfig:
        neurons = self._build_neurons()
        populations = self._build_populations(neurons)
        connections = self._build_connections(populations)
        background_inputs = self._build_background_inputs(populations)

        return NetworkConfig(
            populations=populations,
            connections=connections,
            background_inputs=background_inputs,
            background_mode=self._directory.background_inputs.background_mode,
            stimuli=self._directory.stimuli.stimuli,
            scaling=self._directory.scaling,
            reference=self._directory.reference,
        )

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------
    def _build_neurons(self) -> dict[str, NeuronConfig]:
        return {
            name: NeuronConfig(
                name=name,
                model=entry.model,
                parameters=entry.parameters,
                psp_conversion_aliases=entry.psp_conversion_aliases,
            )
            for name, entry in self._directory.neurons.neurons.items()
        }

    def _build_populations(
        self,
        neurons: dict[str, NeuronConfig],
    ) -> dict[str, PopulationConfig]:
        populations: dict[str, PopulationConfig] = {}

        for entry in self._directory.populations.populations:
            if entry.neuron not in neurons:
                raise ValueError(
                    f"Population '{entry.name}' references neuron '{entry.neuron}', "
                    "which is not defined in neurons.yaml."
                )
            if entry.name in populations:
                raise ValueError(f"Duplicate population name '{entry.name}'.")

            populations[entry.name] = PopulationConfig(
                name=entry.name,
                size=entry.size,
                neuron=neurons[entry.neuron],
                V0_mean=entry.V0_mean,
                V0_std=entry.V0_std,
                background_indegree=entry.background_indegree,
            )

        return populations

    def _build_connections(
        self,
        populations: dict[str, PopulationConfig],
    ) -> list[ConnectionConfig]:
        for connection in self._directory.connectivity.connections:
            for role, name in (
                ("source", connection.source),
                ("target", connection.target),
            ):
                if name not in populations:
                    raise ValueError(
                        f"Connection {role} population '{name}' is not defined "
                        "in populations.yaml."
                    )

        return list(self._directory.connectivity.connections)

    def _build_background_inputs(
        self,
        populations: dict[str, PopulationConfig],
    ) -> dict[str, BackgroundInputConfig]:
        for population_name in self._directory.background_inputs.background_inputs:
            if population_name not in populations:
                raise ValueError(
                    f"background_inputs.yaml references population '{population_name}', "
                    "which is not defined in populations.yaml."
                )

        return dict(self._directory.background_inputs.background_inputs)
