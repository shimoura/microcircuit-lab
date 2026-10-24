"""Simulator backends and backend selection."""

from __future__ import annotations

from pathlib import Path

import numpy as np

# The names are listed with the simulation config, which validates them.
from microcircuit_lab.config.simulation import BackendName

from .interface import SimulationBackend


def get_backend(name: BackendName):
    """Return a backend class by name without importing optional backends eagerly."""
    if name == "nest":
        from .nest.simulator import NestBackend
        return NestBackend
    if name == "brian2":
        from .brian2.simulator import Brian2Backend
        return Brian2Backend
    raise ValueError(f"Unknown simulation backend: {name!r}.")


def read_saved_spikes(name: BackendName, recordings_dir: Path) -> tuple[np.ndarray, np.ndarray]:
    """The spikes a finished run of backend ``name`` saved in ``recordings_dir``,
    as ``(senders, times)`` sorted by sender (see ``backends/population_spikes.py``).

    Only file reading happens here, so a saved run can be analysed without the
    simulator installed."""
    if name == "nest":
        from .nest.spike_files import read_saved_spikes as read_nest_spikes
        return read_nest_spikes(recordings_dir)
    if name == "brian2":
        from .brian2.spike_files import read_saved_spikes as read_brian2_spikes
        return read_brian2_spikes(recordings_dir)
    raise ValueError(f"Unknown simulation backend: {name!r}.")


__all__ = ["BackendName", "SimulationBackend", "get_backend", "read_saved_spikes"]
