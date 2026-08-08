"""Simulator backends and backend selection."""

from __future__ import annotations

from typing import Literal

from .base import SimulationBackend

#: Registered backend names. Adding a backend means adding it here and to
#: get_backend() below -- see "Adding a backend" in the README.
BackendName = Literal["nest"]


def get_backend(name: BackendName):
    """Return a backend class by name without importing optional backends eagerly."""
    if name == "nest":
        from .nest import NestBackend
        return NestBackend
    raise ValueError(f"Unknown simulation backend: {name!r}.")


__all__ = ["BackendName", "SimulationBackend", "get_backend"]
