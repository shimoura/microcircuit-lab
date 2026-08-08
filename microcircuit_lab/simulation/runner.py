"""
Simulation orchestration.

This module coordinates configuration loading,
parameter derivation, network construction and
simulation execution.

It intentionally contains no neuroscience
mathematics and no simulator-specific code.
"""

from __future__ import annotations

from typing import Any

from microcircuit_lab.backends import BackendName, SimulationBackend, get_backend
from microcircuit_lab.network import Network

from microcircuit_lab.io.config import NetworkConfigLoader
from microcircuit_lab.network.preprocessing import NetworkPreprocessor

from microcircuit_lab.config.simulation import SimulationConfig

from microcircuit_lab.io.files import (
    read_network_directory,
    read_yaml,
)
from microcircuit_lab.io.output import resolve_run_directory, save_run_outputs

from pathlib import Path


class Simulation:
    """
    High-level simulation orchestrator.
    """

    def __init__(
        self,
        network: Network,
        simulation_config: SimulationConfig,
        backend: BackendName = "nest",
        backend_options: dict[str, Any] | None = None,
        network_name: str = "network",
        simulation_name: str = "simulation",
    ) -> None:

        self.network = network
        self.simulation_config = simulation_config
        self.backend_name = backend
        self.backend_options = backend_options
        self.network_name = network_name
        self.simulation_name = simulation_name
        self.backend: SimulationBackend | None = None
        self.output_dir: Path | None = None

    @classmethod
    def from_yaml(
        cls,
        config_dir: str | Path = "configs",
        network_name: str = "toy",
        simulation_name: str = "toy",
        backend: BackendName = "nest",
        backend_options: dict[str, Any] | None = None,
    ) -> "Simulation":
        """
        Build a Simulation from YAML files.

        ``backend_options`` is forwarded unchanged to the chosen
        backend's constructor as extra keyword arguments (see
        SimulationBackend); it's for whatever that specific backend
        needs beyond ``network``/``simulation_config``, e.g. NestBackend's
        ``extension_modules`` for loading compiled NEST/NESTML models.
        """

        network_files = read_network_directory(
            Path(config_dir) / "network" / network_name
        )

        network_config = NetworkConfigLoader(
            network_files,
        ).build()

        network_config = NetworkPreprocessor(
            network_config,
        ).process()

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
            backend=backend,
            backend_options=backend_options,
            network_name=network_name,
            simulation_name=simulation_name,
        )

    def run(self) -> None:
        """
        Run the simulation and save its outputs.

        Which artifacts are written (recordings, resolved config,
        metadata) is controlled by ``simulation_config.recording`` and
        ``simulation_config.output``; see :func:`microcircuit_lab.io.output.save_run_outputs`.
        """

        backend_class = get_backend(self.backend_name)
        self.backend = backend_class(
            network=self.network,
            simulation_config=self.simulation_config,
            **(self.backend_options or {}),
        )

        self.output_dir = resolve_run_directory(
            self.simulation_config.output,
            network_name=self.network_name,
            simulation_name=self.simulation_name,
        )
        self.backend.prepare_output(self.output_dir)

        self.backend.build()

        self.backend.simulate()

        self.backend.print_statistics()

        save_run_outputs(
            run_dir=self.output_dir,
            network=self.network,
            simulation_config=self.simulation_config,
            backend=self.backend,
            network_name=self.network_name,
            simulation_name=self.simulation_name,
            backend_name=self.backend_name,
        )