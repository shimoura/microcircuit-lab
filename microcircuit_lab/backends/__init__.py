"""Simulator backends and backend selection."""

from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np

# The names are listed with the simulation config, which validates them.
from microcircuit_lab.config.simulation import BackendName

from .interface import SimulationBackend


def _import_backend(name: str, module: str):
    """Import ``backends/<name>/<module>.py``. A copy of the core made by
    ``init --with-core`` has only the backends of the installed simulators; a
    missing backend folder says so, while a simulator that is not installed
    keeps its own error."""
    try:
        return importlib.import_module(f"{__name__}.{name}.{module}")
    except ModuleNotFoundError as error:
        if error.name != f"{__name__}.{name}":
            raise
        raise ModuleNotFoundError(
            f"This copy of the core has no {name} backend (init --with-core copies only "
            f"the installed simulators). Add it with: "
            f"microcircuit-lab init <project> --with-core --backends {name}"
        ) from None


def get_backend(name: BackendName):
    """Return a backend class by name without importing optional backends eagerly."""
    if name == "nest":
        return _import_backend("nest", "simulator").NestBackend
    if name == "brian2":
        return _import_backend("brian2", "simulator").Brian2Backend
    raise ValueError(f"Unknown simulation backend: {name!r}.")


def read_saved_spikes(name: BackendName, recordings_dir: Path) -> tuple[np.ndarray, np.ndarray]:
    """The spikes a finished run of backend ``name`` saved in ``recordings_dir``,
    as ``(senders, times)`` sorted by sender (see ``backends/spikes.py``).

    Only file reading happens here, so a saved run can be analysed without the
    simulator installed."""
    if name == "nest":
        return _import_backend("nest", "spike_files").read_saved_spikes(recordings_dir)
    if name == "brian2":
        return _import_backend("brian2", "spike_files").read_saved_spikes(recordings_dir)
    raise ValueError(f"Unknown simulation backend: {name!r}.")


def read_saved_variable(
    name: BackendName, recordings_dir: Path, variable: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """A variable a finished run of backend ``name`` recorded (``recording.variables``),
    as ``(senders, times, values)`` sorted by sender, then time. Times are in ms; values
    are in mV, pA, nS, ms or Hz where the variable has that dimension, as in the config
    files (NEST gives the units of its model).

    Only file reading happens here, so a saved run can be analysed without the
    simulator installed."""
    if name == "nest":
        return _import_backend("nest", "spike_files").read_saved_variable(recordings_dir, variable)
    if name == "brian2":
        return _import_backend("brian2", "spike_files").read_saved_variable(recordings_dir, variable)
    raise ValueError(f"Unknown simulation backend: {name!r}.")


__all__ = ["BackendName", "SimulationBackend", "get_backend", "read_saved_spikes", "read_saved_variable"]
