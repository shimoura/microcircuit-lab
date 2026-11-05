"""Areas of a multi-area network: the ``<area>`` in ``<area>__<population>`` names."""

from __future__ import annotations


def list_areas(run):
    """
    The areas of a multi-area network, in population order.

    An area is the ``<area>`` in a population named ``<area>__<population>``.
    Next to such names, a population without ``__`` (e.g. ``TC``) is an area
    of its own; a network where no name has ``__`` has no areas.

    Parameters
    ----------
    run
        A finished run, from :func:`~microcircuit_lab.read_run`.

    Returns
    -------
    list of str
        The area names; empty for a single-area network.
    """
    if not any("__" in name for name in run.populations):
        return []
    areas = []
    for name in run.populations:
        area = name.partition("__")[0]
        if area not in areas:
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
        An area name (see :func:`list_areas`); selects the populations named
        ``<area>__...``, or the population of that name.

    Returns
    -------
    list of str
        The population names.

    Raises
    ------
    ValueError
        If a population or the area does not exist.
    """
    available = list(run.populations)
    if populations is not None:
        missing = set(populations) - set(available)
        if missing:
            raise ValueError(f"Unknown populations: {sorted(missing)}")
        return list(populations)
    if area is not None:
        selected = [name for name in available if name.partition("__")[0] == area]
        if not selected:
            raise ValueError(f"No populations found for area {area!r}.")
        return selected
    return available
