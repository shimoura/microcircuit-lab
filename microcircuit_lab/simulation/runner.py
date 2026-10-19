"""
Simulation orchestration.

This module coordinates configuration loading,
parameter derivation, network construction and
simulation execution.

It intentionally contains no neuroscience
mathematics and no simulator-specific code.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from microcircuit_lab.backends import BackendName, SimulationBackend, get_backend
from microcircuit_lab.backends.post_hoc import PostHocBackend

from microcircuit_lab.network.load import load_network

from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.config.simulation import SimulationConfig

from microcircuit_lab.yaml_files import read_yaml
from microcircuit_lab.runs import save_run_outputs, share_run_directory

from pathlib import Path

logger = logging.getLogger(__name__)


class Simulation:
    """
    High-level simulation orchestrator.
    """

    def __init__(
        self,
        network: NetworkConfig,
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
        # False on every MPI process but the first, which alone saves and plots.
        self.is_main_process = True

    @classmethod
    def from_yaml(
        cls,
        config_dir: str | Path = "configs",
        network_name: str = "toy",
        simulation_name: str | None = None,
        backend: BackendName = "nest",
        backend_options: dict[str, Any] | None = None,
    ) -> "Simulation":
        """
        Build a simulation from the config files.

        Parameters
        ----------
        config_dir
            The folder holding ``network/``, ``simulation/`` and ``analysis/``.
        network_name
            The network folder, ``<config_dir>/network/<network_name>/``.
        simulation_name
            The simulation profile, ``<config_dir>/simulation/<simulation_name>.yaml``.
            By default the same name as the network. If that default file doesn't
            exist, the defaults of ``SimulationConfig()`` are used (with a warning), so
            a new network runs before it has a profile; a profile named explicitly
            must exist.
        backend
            The simulator, ``"nest"``.
        backend_options
            Extra keyword arguments for the backend, passed through unchanged, e.g.
            ``{"extension_modules": ["my_module"]}`` to load a NESTML model in NEST.

        Returns
        -------
        Simulation
            Ready to ``run()``; the network is already loaded and prepared.
        """

        profile_is_explicit = simulation_name is not None
        simulation_name = network_name if simulation_name is None else simulation_name

        network = load_network(Path(config_dir) / "network" / network_name)

        simulation_path = Path(config_dir) / "simulation" / f"{simulation_name}.yaml"
        if simulation_path.exists():
            simulation_config = SimulationConfig.model_validate(read_yaml(simulation_path))
        elif profile_is_explicit:
            raise FileNotFoundError(f"No simulation profile at {simulation_path}.")
        else:
            logger.warning(
                "No simulation profile at %s; using the default settings.", simulation_path
            )
            simulation_config = SimulationConfig()

        return cls(
            network=network,
            simulation_config=simulation_config,
            backend=backend,
            backend_options=backend_options,
            network_name=network_name,
            simulation_name=simulation_name,
        )

    @classmethod
    def from_run_dir(cls, run_dir: str | Path) -> "Simulation":
        """
        Open a finished run to analyse or re-plot it, without simulating again.

        The run's ``config.yaml`` already holds the prepared network, so it is not
        prepared a second time (that would apply the scaling twice). The returned
        simulation reads its spikes from ``<run_dir>/recordings`` (a
        ``PostHocBackend``), and its ``output_dir`` is ``run_dir``, so new plots
        land in that run's ``plots/`` folder.

        Parameters
        ----------
        run_dir
            The run folder, e.g. ``output/toy/20261018_120000``.

        Returns
        -------
        Simulation
            A simulation whose ``run()`` is never called.

        Raises
        ------
        ValueError
            If the run has no ``config.yaml`` (it was saved with
            ``save_config: false``), or its ``metadata.json`` lacks the
            ``first_gid`` of each population (a run saved before this
            existed).
        """

        run_dir = Path(run_dir)
        config_path = run_dir / "config.yaml"
        if not config_path.exists():
            raise ValueError(
                f"No config.yaml in {run_dir} -- was this run saved with "
                "output.save_config=False? Simulation.from_run_dir needs it."
            )

        resolved = read_yaml(config_path)
        network = NetworkConfig.model_validate(resolved["network"])
        simulation_config = SimulationConfig.model_validate(resolved["simulation"])
        backend = PostHocBackend(run_dir)

        network_name, simulation_name, backend_name = run_dir.name, run_dir.name, "nest"
        metadata_path = run_dir / "metadata.json"
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text())
            network_name = metadata.get("network_name", network_name)
            simulation_name = metadata.get("simulation_name", simulation_name)
            backend_name = metadata.get("backend", backend_name)

        simulation = cls(
            network=network,
            simulation_config=simulation_config,
            backend=backend_name,
            network_name=network_name,
            simulation_name=simulation_name,
        )
        simulation.backend = backend
        simulation.output_dir = run_dir
        return simulation

    def run(self) -> None:
        """
        Build the network in the simulator, simulate it and save the outputs.

        What is saved (recordings, the prepared config, metadata) is set by the
        ``recording`` and ``output`` sections of the simulation config; see
        :func:`microcircuit_lab.runs.save_run_outputs`. ``output_dir`` points to the
        run folder afterwards. With several MPI processes, only the first prints and
        saves; the others have ``is_main_process`` False.
        """

        backend_class = get_backend(self.backend_name)
        self.backend = backend_class(
            network=self.network,
            simulation_config=self.simulation_config,
            **(self.backend_options or {}),
        )
        self.is_main_process = self.backend.rank() == 0
        self.output_dir = share_run_directory(
            self.simulation_config.output,
            network_name=self.network_name,
            simulation_name=self.simulation_name,
            backend=self.backend,
        )
        self.backend.prepare_output(self.output_dir)

        self.backend.build()

        self.backend.simulate()

        # Each process writes its own recording files; they are complete only
        # once every process has finished simulating.
        self.backend.sync_processes()
        if not self.is_main_process:
            return

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