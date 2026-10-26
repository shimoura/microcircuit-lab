"""Simulator backends and backend selection."""

from __future__ import annotations

import json
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


def read_recording(run_dir: Path, variable: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    A variable that a finished run recorded (``recording.variables``), read
    from the files of ``run_dir`` without the simulator installed.

    Parameters
    ----------
    run_dir
        The run folder, with its ``metadata.json`` and ``recordings/``.
    variable
        The variable's name, as in ``recording.variables`` (e.g. ``"V_m"``).

    Returns
    -------
    senders, times, values
        Node IDs, times (ms) and values of every sample, sorted by sender, then
        time. Values are in mV, pA, nS, ms or Hz where the variable has that
        dimension, as in the config files; NEST gives the units of its model.
    """

    run_dir = Path(run_dir)
    metadata_path = run_dir / "metadata.json"
    if not metadata_path.exists():
        raise ValueError(f"No metadata.json in {run_dir}, which tells the simulator of the run.")
    name = json.loads(metadata_path.read_text())["backend"]
    recordings_dir = run_dir / "recordings"
    if name == "nest":
        from .nest.spike_files import read_saved_variable as read_nest_variable
        return read_nest_variable(recordings_dir, variable)
    if name == "brian2":
        from .brian2.spike_files import read_saved_variable as read_brian2_variable
        return read_brian2_variable(recordings_dir, variable)
    raise ValueError(f"Unknown simulation backend: {name!r}.")


__all__ = ["BackendName", "SimulationBackend", "get_backend", "read_recording", "read_saved_spikes"]
