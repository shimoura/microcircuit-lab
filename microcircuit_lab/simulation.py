"""
The ``Simulation`` class: loads the config files, builds the network in a
backend, runs it and saves the results.

It holds no neuroscience maths and no simulator-specific code.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from microcircuit_lab.backends import BackendName, SimulationBackend, get_backend
from microcircuit_lab.backends.run_folder_reader import RunFolderReader
from microcircuit_lab.config.connection_table import ConnectionTable
from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.config.simulation import BackendConfig, SimulationConfig
from microcircuit_lab.network.load import read_network
from microcircuit_lab.run_folder import save_run_outputs, share_run_directory
from microcircuit_lab.yaml_files import read_yaml

logger = logging.getLogger(__name__)


class Simulation:
    """A network and its simulation settings, run on a backend."""

    def __init__(
        self,
        network: NetworkConfig,
        simulation_config: SimulationConfig,
        backend: BackendName | None = None,
        backend_options: dict[str, Any] | None = None,
        network_name: str = "network",
        simulation_name: str = "simulation",
    ) -> None:

        self.network = network
        self.simulation_config = _with_backend(simulation_config, backend, backend_options)
        self.network_name = network_name
        self.simulation_name = simulation_name
        self.backend: SimulationBackend | None = None
        self.output_dir: Path | None = None
        # False on every MPI process but the first, which alone saves and plots.
        self.is_main_process = True

    @property
    def backend_name(self) -> BackendName:
        """The simulator, from the ``backend`` section of the simulation config."""
        return self.simulation_config.backend.name

    @property
    def backend_options(self) -> dict[str, Any]:
        """The simulator's options, from the ``backend`` section of the simulation config."""
        return self.simulation_config.backend.options

    @classmethod
    def from_yaml(
        cls,
        config_dir: str | Path = "configs",
        network_name: str = "toy",
        simulation_name: str | None = None,
        backend: BackendName | None = None,
        backend_options: dict[str, Any] | None = None,
    ) -> Simulation:
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
            The simulator, ``"nest"`` or ``"brian2"``. By default the one in the
            ``backend`` section of the simulation profile (``"nest"`` without it).
        backend_options
            Extra keyword arguments for the backend, passed through unchanged, e.g.
            ``{"nest_modules": ["my_module"]}`` to load a NESTML model in NEST.
            They replace the profile's options of the same name. The profile's
            options are dropped when ``backend`` names another simulator.

        Returns
        -------
        Simulation
            Ready to ``run()``; the network is already read.
        """

        profile_is_explicit = simulation_name is not None
        simulation_name = network_name if simulation_name is None else simulation_name

        network = read_network(Path(config_dir) / "network" / network_name)

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
    def from_run_dir(cls, run_dir: str | Path) -> Simulation:
        """
        Open a finished run to analyse or re-plot it, without simulating again.

        The run's ``config.yaml`` holds the network as it was simulated. The returned
        simulation reads its spikes from ``<run_dir>/recordings`` (a
        ``RunFolderReader``), and its ``output_dir`` is ``run_dir``, so new plots
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
        FileNotFoundError
            If ``run_dir`` does not exist.
        ValueError
            If the run has no ``config.yaml`` (it was saved with
            ``save_config: false``), or its ``metadata.json`` lacks the
            ``first_gid`` of each population (simulate the run again).
        """

        run_dir = Path(run_dir)
        if not run_dir.is_dir():
            raise FileNotFoundError(f"No run folder at {run_dir}.")
        config_path = run_dir / "config.yaml"
        if not config_path.exists():
            raise ValueError(
                f"No config.yaml in {run_dir}: the run was saved with "
                "output.save_config: false, so it cannot be re-plotted."
            )

        resolved = read_yaml(config_path)
        # A large network's connections are in a CSV file next to config.yaml.
        if "connections_file" in resolved["network"]:
            name = resolved["network"].pop("connections_file")
            csv_path = run_dir / name
            if not csv_path.is_file():
                raise FileNotFoundError(
                    f"{run_dir}: config.yaml names connections_file '{name}', but there is "
                    f"no file {csv_path}."
                )
            resolved["network"]["connections"] = ConnectionTable.read_csv(csv_path)
        network = NetworkConfig.model_validate(resolved["network"])
        simulation_config = SimulationConfig.model_validate(resolved["simulation"])
        backend = RunFolderReader(run_dir)

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

        What is saved (recordings, the config, metadata) is set by the
        ``recording`` and ``output`` sections of the simulation config; see
        :func:`microcircuit_lab.run_folder.save_run_outputs`. ``output_dir`` points to the
        run folder afterwards. With several MPI processes, only the first prints and
        saves; the others have ``is_main_process`` False.
        """

        backend_class = get_backend(self.backend_name)
        self.backend = backend_class(
            network=self.network,
            simulation_config=self.simulation_config,
            **self.backend_options,
        )
        self.backend.check()
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


def _with_backend(
    simulation_config: SimulationConfig,
    backend: BackendName | None,
    backend_options: dict[str, Any] | None,
) -> SimulationConfig:
    """``simulation_config`` with the simulator actually used, so the run's
    ``config.yaml`` records it: ``backend`` and ``backend_options`` win over the
    config's ``backend`` section, whose options belong to its own simulator only."""

    configured = simulation_config.backend
    for given in (configured.options, backend_options or {}):
        if "extension_modules" in given:
            raise ValueError(
                "The backend option extension_modules was split in two: nest_modules for "
                "compiled NEST modules (e.g. from NESTML), extensions for Python modules "
                "with Brian2 models."
            )
    if backend is None:
        backend = configured.name
    options = configured.options if backend == configured.name else {}
    options = {**options, **(backend_options or {})}
    return simulation_config.model_copy(
        update={"backend": BackendConfig(name=backend, options=options)}
    )
