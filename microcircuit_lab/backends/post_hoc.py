"""
Read-only backend for post-hoc analysis: re-analyzing a saved run's
spikes after the fact, without re-simulating.

Reconstructs the read side of the SimulationBackend contract
(get_population/get_spike_events) from files a run already wrote
(metadata.json, recordings/) instead of a live simulator. See
Simulation.from_run_dir, the only place this is meant to be constructed.

This is deliberately not registered in backends.get_backend/BackendName:
it never drives a simulation, so it isn't a choice one makes for
Simulation.from_yaml the way a simulator is. The spike files are read by
the backend that wrote them (its name is in metadata.json), see
backends.read_saved_spikes.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from microcircuit_lab.backends import read_saved_spikes, spikes


class PostHocBackend:
    """Replays spikes recorded by a previous run, for post-hoc analysis.
    Read-only: every method that would drive a simulation
    (build/simulate/...) raises."""

    def __init__(self, run_dir: str | Path) -> None:
        self.run_dir = Path(run_dir)
        self._recordings_dir = self.run_dir / "recordings"

        metadata_path = self.run_dir / "metadata.json"
        if not metadata_path.exists():
            raise ValueError(
                f"No metadata.json in {self.run_dir} -- was this run saved with "
                "output.save_metadata=False? PostHocBackend needs it to recover "
                "each population's node-ID range."
            )
        self._metadata = json.loads(metadata_path.read_text())

        missing_gid = [
            name for name, stats in self._metadata.get("populations", {}).items()
            if "first_gid" not in stats
        ]
        if missing_gid:
            raise ValueError(
                f"metadata.json in {self.run_dir} has no 'first_gid' for "
                f"population(s) {missing_gid}. Simulate the run again to write it."
            )
        self._cached_spikes: tuple[np.ndarray, np.ndarray] | None = None

    def get_population(self, name: str) -> np.ndarray:
        """Return this population's node IDs as a contiguous range, anchored
        at metadata.json's 'first_gid' (see write_run_metadata)."""

        stats = self._metadata["populations"][name]
        first_gid = stats["first_gid"]
        return np.arange(first_gid, first_gid + stats["size"])

    def _load_spikes(self) -> tuple[np.ndarray, np.ndarray]:
        """The spikes of the run as (senders, times), sorted by sender. Read once."""

        if self._cached_spikes is None:
            self._cached_spikes = read_saved_spikes(
                self._metadata["backend"], self._recordings_dir
            )
        return self._cached_spikes

    def get_spike_events(self, population: str) -> dict:
        """Return {"senders": ..., "times": ...} read back from whatever
        this run wrote for `population`."""

        if population not in self._metadata.get("populations", {}):
            raise ValueError(f"Unknown population {population!r} in metadata.")

        senders, times = self._load_spikes()
        stats = self._metadata["populations"][population]
        first_gid = stats["first_gid"]
        return spikes.spikes_in_id_range(senders, times, first_gid, first_gid + stats["size"] - 1)

    def version(self) -> str | None:
        """The simulator version recorded in metadata.json, if the run has one."""

        return self._metadata.get("simulator_version")

    def num_processes(self) -> int:
        return 1

    def rank(self) -> int:
        return 0

    def sync_processes(self) -> None:
        pass

    def prepare_output(self, run_dir: Path) -> None:
        raise NotImplementedError("PostHocBackend is read-only; it replays a finished run.")

    def build(self) -> None:
        raise NotImplementedError("PostHocBackend is read-only; it replays a finished run.")

    def simulate(self) -> None:
        raise NotImplementedError("PostHocBackend is read-only; it replays a finished run.")

    def print_statistics(self) -> None:
        raise NotImplementedError("PostHocBackend is read-only; it replays a finished run.")

    def save_recordings(self, run_dir: Path) -> list[Path]:
        raise NotImplementedError("PostHocBackend is read-only; it replays a finished run.")
