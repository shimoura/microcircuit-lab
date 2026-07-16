"""Simulator backends and backend selection."""

from __future__ import annotations

from typing import TypeAlias

from .base import SimulationBackend

BackendName: TypeAlias = str


def get_backend(name: BackendName):
    """Return a backend class by name without importing optional backends eagerly."""
    if name == "nest":
        from .nest import NestBackend
        return NestBackend
    raise ValueError(f"Unknown simulation backend: {name!r}.")


__all__ = ["BackendName", "SimulationBackend", "get_backend"]
