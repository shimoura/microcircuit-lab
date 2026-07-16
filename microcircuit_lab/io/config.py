"""
Build validated NetworkConfig objects from raw configuration dictionaries.

This builder resolves references between the different YAML configuration
files (e.g. populations -> neurons) and constructs the immutable
NetworkConfig used by the rest of the project.

No numerical parameter derivation is performed here.
No simulator-specific code belongs here.
"""

from __future__ import annotations

from microcircuit_lab.config.network import (
    ConnectionConfig,
    DelayDistribution,
    NetworkConfig,
    NeuronConfig,
    NeuronParams,
    PoissonInputConfig,
    PopulationConfig,
    ScalingConfig,
    WeightDistribution,
    ReferenceConfig,
)

from microcircuit_lab.io.files import NetworkFiles


class NetworkConfigLoader:
    """
    Build a validated NetworkConfig from raw dictionaries.
    """

    def __init__(
        self,
        network_files: NetworkFiles,
    ) -> None:
        self._populations_data = network_files.populations
        self._neurons_data = network_files.neurons
        self._connectivity_data = network_files.connectivity
        self._inputs_data = network_files.inputs
        self._scaling_data = network_files.scaling
        self._reference_data = network_files.reference

    def build(self) -> NetworkConfig:
        """
        Construct the immutable NetworkConfig.
        """

        neurons = self._build_neurons()

        populations = self._build_populations(neurons)

        connections = self._build_connections(populations)

        inputs = self._build_inputs(populations)

        scaling = ScalingConfig.model_validate(self._scaling_data)
        reference = ReferenceConfig.model_validate(self._reference_data)

        return NetworkConfig(
            populations=populations,
            connections=connections,
            inputs=inputs,
            scaling=scaling,
            reference=reference
        )

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------
    def _build_neurons(self) -> dict[str, NeuronConfig]:
        """
        Build all neuron definitions.
        """

        neuron_configs: dict[str, NeuronConfig] = {}

        neuron_dict = self._neurons_data.get("neurons", {})

        for name, values in neuron_dict.items():

            params = NeuronParams.model_validate(values["parameters"])

            neuron_configs[name] = NeuronConfig(
                name=name,
                model=values["model"],
                parameters=params,
            )

        return neuron_configs

    def _build_populations(
        self,
        neurons: dict[str, NeuronConfig],
    ) -> dict[str, PopulationConfig]:
        """
        Build all populations and resolve neuron references.
        """

        populations: dict[str, PopulationConfig] = {}

        for values in self._populations_data.get("populations", []):

            neuron_name = values["neuron"]

            if neuron_name not in neurons:
                raise ValueError(
                    f"Unknown neuron definition '{neuron_name}' "
                    f"referenced by population '{values['name']}'."
                )

            population = PopulationConfig(
                name=values["name"],
                size=values["size"],
                neuron=neurons[neuron_name],
                V0_mean=values["V0_mean"],
                V0_std=values["V0_std"],
                background_indegree=values.get(
                    "background_indegree",
                    0.0,
                ),
            )

            if population.name in populations:
                raise ValueError(f"Duplicate population name '{population.name}'.")
            populations[population.name] = population

        return populations

    def _build_connections(
        self,
        populations: dict[str, PopulationConfig],
    ) -> list[ConnectionConfig]:
        """
        Build all recurrent connections.
        """

        connections: list[ConnectionConfig] = []

        for values in self._connectivity_data.get("connections", []):

            source = values["source"]
            target = values["target"]

            if source not in populations:
                raise ValueError(f"Unknown source population '{source}'.")

            if target not in populations:
                raise ValueError(f"Unknown target population '{target}'.")

            connections.append(
                ConnectionConfig(
                    source=source,
                    target=target,
                    n_synapses=values["n_synapses"],
                    weight=WeightDistribution.model_validate(values["weight"]),
                    delay=DelayDistribution.model_validate(values["delay"]),
                )
            )

        return connections

    def _build_inputs(
        self,
        populations: dict[str, PopulationConfig],
    ) -> dict[str, PoissonInputConfig]:
        """
        Build background input definitions.
        """

        inputs: dict[str, PoissonInputConfig] = {}

        for population_name, values in self._inputs_data.get(
            "inputs",
            {},
        ).items():

            if population_name not in populations:
                raise ValueError(
                    f"Unknown population '{population_name}' "
                    "referenced in inputs.yaml."
                )

            inputs[population_name] = PoissonInputConfig(
                rate=values["rate"],
                weight=WeightDistribution.model_validate(
                    values["weight"]
                ),
                delay=DelayDistribution.model_validate(
                    values["delay"]
                ),
            )

        return inputs
