"""
Simulation orchestration.

This module coordinates configuration loading,
parameter derivation, network construction and
simulation execution.

It intentionally contains no neuroscience
mathematics and no simulator-specific code.
"""

from __future__ import annotations

from human_microcircuit.backend.nest.backend import NestBackend
from human_microcircuit.network.network import Network

from human_microcircuit.builders.config_builder import ConfigBuilder
from human_microcircuit.builders.parameter_builder import ParameterBuilder

from human_microcircuit.config.simulation import SimulationConfig

from human_microcircuit.utils.io import (
    read_network_directory,
    read_yaml,
)

from pathlib import Path


class Simulation:
    """
    High-level simulation orchestrator.
    """

    def __init__(
        self,
        network: Network,
        simulation_config: SimulationConfig,
    ) -> None:

        self.network = network
        self.simulation_config = simulation_config
        self.backend: NestBackend | None = None

    @classmethod
    def from_yaml(
        cls,
        config_dir: str | Path = "configs",
        network_name: str = "toy",
        simulation_name: str = "default",
    ) -> "Simulation":
        """
        Build a Simulation from YAML files.
        """

        network_files = read_network_directory(
            Path(config_dir) / "network" / network_name
        )

        network_config = ConfigBuilder(
            network_files,
        ).build()

        network_config = ParameterBuilder(
            network_config,
        ).build()

        network = Network(
            network_config,
        )

        simulation_data = read_yaml(
            Path(config_dir) / "simulation" / f"{simulation_name}.yaml"
        )

        simulation_config = SimulationConfig.model_validate(simulation_data)

        return cls(
            network=network,
            simulation_config=simulation_config,
        )

    def run(self) -> None:
        """
        Run the simulation.
        """

        self.backend = NestBackend(
            network=self.network,
            simulation_config=self.simulation_config,
        )

        self.backend.build()

        self.backend.simulate()

        self.backend.print_statistics()


    def get_spike_events(
        self,
        population: str,
    ):
        """
        Return native NEST spike events.
        """

        if self.backend is None:
            raise RuntimeError(
                "Simulation has not been run yet."
            )

        return self.backend.get_spike_events(population)