"""
Read a finished run folder: its spikes, recordings and the settings it was
simulated with. No simulator is needed.

``read_run`` is how the plots read a run, and how you read it in your own
analyses::

    from microcircuit_lab import read_run

    run = read_run("output/toy/20261018_120000")
    spikes = run.spikes("E")        # senders, times (ms)
    trace = run.recording("V_m")    # senders, times (ms), values
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple

import numpy as np

from microcircuit_lab.backends import read_saved_spikes, read_saved_variable
from microcircuit_lab.backends.spikes import spikes_in_id_range
from microcircuit_lab.config.connection_table import ConnectionTable
from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.config.simulation import SimulationConfig
from microcircuit_lab.config.yaml_files import read_yaml


class Spikes(NamedTuple):
    """Spikes as two arrays, sorted by sender, then time."""

    senders: np.ndarray  # node IDs
    times: np.ndarray  # ms


class Recording(NamedTuple):
    """Samples of a recorded variable, sorted by sender, then time."""

    senders: np.ndarray  # node IDs
    times: np.ndarray  # ms
    values: np.ndarray  # in the unit of the config files (NEST: of its model)


class Run:
    """
    A finished run, read from its folder with :func:`read_run`.

    Attributes
    ----------
    folder : pathlib.Path
        The run folder.
    populations : list of str
        The population names, in network order.
    network : NetworkConfig
        The network as it was simulated (from ``config.yaml``).
    simulation : SimulationConfig
        The simulation settings (from ``config.yaml``).
    metadata : dict
        The content of ``metadata.json``: the simulator, the seed, the spike
        statistics of each population, the files of the run.
    """

    def __init__(
        self,
        folder: Path,
        network: NetworkConfig,
        simulation: SimulationConfig,
        metadata: dict,
    ) -> None:
        self.folder = folder
        self.populations = list(network.populations)
        self.network = network
        self.simulation = simulation
        self.metadata = metadata
        self._spikes: Spikes | None = None

    def node_ids(self, population: str) -> np.ndarray:
        """The node IDs of a population: one block, ``first_node_id`` to ``last_node_id`` in ``metadata.json``."""

        stats = self._population_stats(population)
        return np.arange(stats["first_node_id"], stats["last_node_id"] + 1)

    def spikes(self, population: str) -> Spikes:
        """
        The spikes of a population.

        Parameters
        ----------
        population
            A name from ``run.populations``.

        Returns
        -------
        Spikes
            ``senders`` (node IDs) and ``times`` (ms), sorted by sender, then time.
        """

        node_ids = self.node_ids(population)
        if not self.simulation.recording.spike_recording:
            raise RuntimeError("Spike recording was disabled for this run.")
        # The spike files hold all populations; they are read once.
        if self._spikes is None:
            self._spikes = Spikes(
                *read_saved_spikes(self.metadata["backend"], self.folder / "recordings")
            )
        return Spikes(**spikes_in_id_range(*self._spikes, node_ids[0], node_ids[-1]))

    def recording(self, variable: str) -> Recording:
        """
        A variable recorded in the run (``recording.variables``).

        Parameters
        ----------
        variable
            The variable's name, as in ``recording.variables`` (e.g. ``"V_m"``).

        Returns
        -------
        Recording
            ``senders`` (node IDs), ``times`` (ms) and ``values`` of every sample,
            sorted by sender, then time. Values are in mV, pA, nS, ms or Hz where the
            variable has that dimension, as in the config files; NEST gives the units
            of its model.
        """

        return Recording(
            *read_saved_variable(
                self.metadata["backend"], self.folder / "recordings", variable
            )
        )

    def _population_stats(self, population: str) -> dict:
        if population not in self.populations:
            raise ValueError(f"Unknown population {population!r}; the run has {self.populations}.")
        return self.metadata["populations"][population]


def read_run(run_dir: str | Path) -> Run:
    """
    Open a finished run folder, without the simulator.

    Parameters
    ----------
    run_dir
        The run folder, e.g. ``output/toy/20261018_120000``.

    Returns
    -------
    Run
        The run's settings, and its spikes and recordings, which are read when asked for.

    Raises
    ------
    FileNotFoundError
        If ``run_dir`` does not exist.
    ValueError
        If the run has no ``config.yaml`` (``output.save_config: false``) or no
        ``metadata.json`` (``output.save_metadata: false``), or the metadata
        lacks the node IDs of a population (simulate the run again).
    """

    folder = Path(run_dir)
    if not folder.is_dir():
        raise FileNotFoundError(f"No run folder at {folder}.")

    config_path = folder / "config.yaml"
    if not config_path.exists():
        raise ValueError(
            f"No config.yaml in {folder}: the run was saved with "
            "output.save_config: false, so it cannot be read."
        )
    metadata_path = folder / "metadata.json"
    if not metadata_path.exists():
        raise ValueError(
            f"No metadata.json in {folder}: the run was saved with "
            "output.save_metadata: false, so it cannot be read. It holds the simulator "
            "and the node-ID range of each population."
        )

    saved = read_yaml(config_path)
    # A large network's connections are in a CSV file next to config.yaml.
    if "connections_file" in saved["network"]:
        name = saved["network"].pop("connections_file")
        csv_path = folder / name
        if not csv_path.is_file():
            raise FileNotFoundError(
                f"{folder}: config.yaml names connections_file '{name}', but there is "
                f"no file {csv_path}."
            )
        saved["network"]["connections"] = ConnectionTable.read_csv(csv_path)
    network = NetworkConfig.model_validate(saved["network"])
    simulation = SimulationConfig.model_validate(saved["simulation"])

    metadata = json.loads(metadata_path.read_text())
    missing = [
        name for name in network.populations
        if "first_node_id" not in metadata.get("populations", {}).get(name, {})
    ]
    if missing:
        raise ValueError(
            f"metadata.json in {folder} has no 'first_node_id' for population(s) {missing}. "
            "Simulate the run again to write it."
        )

    return Run(folder, network, simulation, metadata)
