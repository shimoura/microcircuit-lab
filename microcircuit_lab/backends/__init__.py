"""Simulator backends and backend selection."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import numpy as np

from .base import SimulationBackend

#: Registered backend names. Adding a backend means adding it here and to
#: get_backend() and read_saved_spikes() below. See "Adding a backend" in the README.
BackendName = Literal["nest"]


def get_backend(name: BackendName):
    """Return a backend class by name without importing optional backends eagerly."""
    if name == "nest":
        from .nest import NestBackend
        return NestBackend
    raise ValueError(f"Unknown simulation backend: {name!r}.")


def read_saved_spikes(name: BackendName, recordings_dir: Path) -> tuple[np.ndarray, np.ndarray]:
    """The spikes a finished run of backend ``name`` saved in ``recordings_dir``,
    as ``(senders, times)`` sorted by sender (see ``backends/spikes.py``).

    Only file reading happens here, so a saved run can be analysed without the
    simulator installed."""
    if name == "nest":
        from .nest_files import read_saved_spikes as read_nest_spikes
        return read_nest_spikes(recordings_dir)
    raise ValueError(f"Unknown simulation backend: {name!r}.")


__all__ = ["BackendName", "SimulationBackend", "get_backend", "read_saved_spikes"]
