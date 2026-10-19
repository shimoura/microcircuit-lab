"""
Read-only backend that replays the spikes of a saved run, so the run can be
analysed again without simulating.

It reads ``metadata.json`` and the ``recordings/`` folder that the run wrote.
Build it with ``Simulation.from_run_dir``. It is not listed in ``get_backend``,
because it cannot run a simulation. The spike files are read as the backend that
wrote them does (its name is in ``metadata.json``); see ``read_saved_spikes``.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from microcircuit_lab.backends import read_saved_spikes, spikes


class PostHocBackend:
    """Replays the spikes of a saved run. Methods that would run a simulation raise."""

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
        """Return the node IDs of a population: a range starting at its ``first_gid`` in ``metadata.json``."""

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
        """Return the spikes of ``population`` as ``{"senders": ..., "times": ...}``."""

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
