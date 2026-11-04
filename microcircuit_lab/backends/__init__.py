"""Simulator backends and backend selection.

Each backend is a folder ``backends/<name>/`` with the same two modules, so
nothing here names a simulator:

- ``simulator.py``: its class, implementing ``SimulationBackend``
  (``interface.py``), also named ``Backend``, which :func:`get_backend` returns;
- ``spike_files.py``: ``read_saved_spikes`` and ``read_saved_variable``, which
  read a finished run's files without importing the simulator.

The backend names are ``BackendName`` (``config/simulation.py``).
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import get_args

import numpy as np

# The names are listed with the simulation config, which validates them.
from microcircuit_lab.config.simulation import BackendName

from .interface import SimulationBackend


def _import_backend(name: str, module: str):
    """Import ``backends/<name>/<module>.py``. A copy of the core made by
    ``init --with-core`` has only the backends of the installed simulators; a
    missing backend folder says so, and so does a simulator that is not
    installed. Any other missing module keeps its own error."""
    if name not in get_args(BackendName):
        raise ValueError(f"Unknown simulation backend: {name!r}.")
    try:
        return importlib.import_module(f"{__name__}.{name}.{module}")
    except ModuleNotFoundError as error:
        # The backend's Python package has the backend's name (nest, brian2).
        if error.name == name:
            raise ModuleNotFoundError(
                f"The {name} backend needs the Python package {name}, which is not installed. "
                f'Install it, e.g. pip install "microcircuit_lab[{name}]" (see Installation '
                "in microcircuit_lab/README.md)."
            ) from None
        if error.name != f"{__name__}.{name}":
            raise
        raise ModuleNotFoundError(
            f"This copy of the core has no {name} backend (init --with-core copies only "
            f"the installed simulators). Add it with: "
            f"microcircuit-lab init <project> --with-core --backends {name}"
        ) from None


def get_backend(name: BackendName):
    """Return a backend class by name without importing optional backends eagerly."""
    return _import_backend(name, "simulator").Backend


def read_saved_spikes(name: BackendName, recordings_dir: Path) -> tuple[np.ndarray, np.ndarray]:
    """The spikes a finished run of backend ``name`` saved in ``recordings_dir``,
    as ``(senders, times)`` sorted by sender (see ``backends/spikes.py``).

    Only file reading happens here, so a saved run can be analysed without the
    simulator installed."""
    return _import_backend(name, "spike_files").read_saved_spikes(recordings_dir)


def read_saved_variable(
    name: BackendName, recordings_dir: Path, variable: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """A variable a finished run of backend ``name`` recorded (``recording.variables``),
    as ``(senders, times, values)`` sorted by sender, then time. Times are in ms; values
    are in mV, pA, nS, ms or Hz where the variable has that dimension, as in the config
    files (NEST gives the units of its model).

    Only file reading happens here, so a saved run can be analysed without the
    simulator installed."""
    return _import_backend(name, "spike_files").read_saved_variable(recordings_dir, variable)


__all__ = ["BackendName", "SimulationBackend", "get_backend", "read_saved_spikes", "read_saved_variable"]
