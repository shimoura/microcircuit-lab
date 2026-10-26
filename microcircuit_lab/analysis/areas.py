"""Areas of a multi-area network: the ``<area>`` in ``<area>__<population>`` names."""

from __future__ import annotations


def list_areas(run):
    """
    The areas of a multi-area network, in population order.

    An area is the ``<area>`` in a population named ``<area>__<population>``;
    a population without ``__`` belongs to no area.

    Parameters
    ----------
    run
        A finished run, from :func:`~microcircuit_lab.read_run`.

    Returns
    -------
    list of str
        The area names; empty for a single-area network.
    """
    areas = []
    for name in run.network.populations:
        area, sep, _ = name.partition("__")
        if sep and area not in areas:
            areas.append(area)
    return areas


def select_populations(run, populations, area):
    """
    The populations to analyse: those given, or those of one area, or all.

    Parameters
    ----------
    run
        A finished run, from :func:`~microcircuit_lab.read_run`.
    populations
        Population names to use; each must exist. Takes precedence over ``area``.
    area
        An area name; selects the populations named ``<area>__...``.

    Returns
    -------
    list of str
        The population names.

    Raises
    ------
    ValueError
        If a population or the area does not exist.
    """
    available = list(run.network.populations)
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
