"""Shared helpers for population-level analyses."""

from __future__ import annotations

#: Sentinel distinguishing "this argument wasn't passed at all" (fall back
#: to the plot's config object) from an explicit value -- including an
#: explicit None, which is itself a meaningful choice for some fields
#: (e.g. xlim=None means "full range", not "unset"). Python has no
#: cleaner built-in way to get this 3-state default; shared here so every
#: plot module uses the same sentinel instead of a differently-named
#: local one each.
UNSET = object()


def list_areas(simulation):
    """Return the areas of a multi-area network, in population order.

    An area is the ``<area>`` part of a ``<area>__<population>`` name;
    populations without ``__`` belong to no area. Empty for single-area networks.
    """
    areas = []
    for name in simulation.network.config.populations:
        area, sep, _ = name.partition("__")
        if sep and area not in areas:
            areas.append(area)
    return areas


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
