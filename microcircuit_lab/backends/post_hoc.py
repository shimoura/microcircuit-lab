"""
Read-only backend for post-hoc analysis: re-analyzing a saved run's
spikes after the fact, without re-simulating.

Reconstructs the read side of the SimulationBackend contract
(get_population/get_spike_events) from files a run already wrote
(metadata.json, recordings/) instead of a live simulator. See
Simulation.from_run_dir, the only place this is meant to be constructed.

This is deliberately not registered in backends.get_backend/BackendName:
it never drives a simulation, so it isn't a choice one makes for
Simulation.from_yaml the way NestBackend is.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


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
                f"population(s) {missing_gid} -- this run predates "
                "PostHocBackend support. Re-run the simulation once to pick up "
                "the new metadata field, then re-analysis will work."
            )
        self._cached_spikes: tuple[np.ndarray, np.ndarray] | None = None

    def get_population(self, name: str) -> np.ndarray:
        """Return this population's node IDs as a contiguous range, anchored
        at metadata.json's 'first_gid' (see write_run_metadata)."""

        stats = self._metadata["populations"][name]
        first_gid = stats["first_gid"]
        return np.arange(first_gid, first_gid + stats["size"])

    def _load_spikes(self) -> tuple[np.ndarray, np.ndarray]:
        """Return all spikes of the run as (senders, times), sorted by sender.

        Reads the ascii shards NEST wrote natively (``spikes-*.dat``) if
        present, else the in-memory-mode fallback (``spikes.csv``). Cached.
        """

        if self._cached_spikes is not None:
            return self._cached_spikes

        ascii_paths = sorted(self._recordings_dir.glob("spikes-*.dat"))
        if ascii_paths:
            senders_list: list[np.ndarray] = []
            times_list: list[np.ndarray] = []
            for path in ascii_paths:
                data = pd.read_csv(path, sep="\t", comment="#")
                senders_list.append(data["sender"].to_numpy())
                times_list.append(data["time_ms"].to_numpy())
            if senders_list:
                senders = np.concatenate(senders_list).astype(int)
                times = np.concatenate(times_list).astype(float)
            else:
                senders = np.array([], dtype=int)
                times = np.array([], dtype=float)

        elif (self._recordings_dir / "spikes.csv").exists():
            data = pd.read_csv(self._recordings_dir / "spikes.csv")
            senders = data["sender"].to_numpy(dtype=int)
            times = data["time_ms"].to_numpy(dtype=float)

        else:
            raise ValueError(
                f"No recordings found under {self._recordings_dir} "
                f"(expected 'spikes-*.dat' or 'spikes.csv'). "
                "This run predates recorder consolidation -- re-run the "
                "simulation once to produce consolidated recordings, then "
                "re-analysis will work."
            )

        if len(senders) > 0:
            order = np.argsort(senders, kind="stable")
            self._cached_spikes = (senders[order], times[order])
        else:
            self._cached_spikes = (np.array([], dtype=int), np.array([], dtype=float))

        return self._cached_spikes

    def get_spike_events(self, population: str) -> dict:
        """Return {"senders": ..., "times": ...} read back from whatever
        this run wrote for `population`."""

        sorted_senders, sorted_times = self._load_spikes()
        if len(sorted_senders) == 0:
            return {"senders": np.array([], dtype=int), "times": np.array([], dtype=float)}

        if population not in self._metadata.get("populations", {}):
            raise ValueError(f"Unknown population {population!r} in metadata.")

        stats = self._metadata["populations"][population]
        first_gid = stats["first_gid"]
        last_gid = first_gid + stats["size"] - 1

        left = np.searchsorted(sorted_senders, first_gid, side="left")
        right = np.searchsorted(sorted_senders, last_gid + 1, side="left")

        return {
            "senders": sorted_senders[left:right],
            "times": sorted_times[left:right],
        }

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
