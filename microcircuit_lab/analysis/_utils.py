"""Shared helpers for population-level analyses."""

from __future__ import annotations


def select_populations(simulation, populations, area):
    """Return validated population names for an optional area selection."""
    available = list(simulation.network.config.populations)
    if populations is not None:
        missing = set(populations) - set(available)
        if missing:
            raise ValueError(f"Unknown populations: {sorted(missing)}")
        return list(populations)
    if area is not None:
        prefix = f"{area}__"
        selected = [name for name in available if name.startswith(prefix)]
        if not selected:
            raise ValueError(f"No populations found for area {area!r}.")
        return selected
    return available
