"""
The ``weight`` and ``delay`` entries of a connection, background input or
stimulus, and the number of synapses from a connection probability.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from microcircuit_lab.config.connectivity import (
    SHARED_DISTRIBUTIONS,
    DelayDistribution,
    WeightDistribution,
)


def _drawn(
    mean: float,
    rel_std: float,
    distribution: str | None,
    arguments: Mapping[str, Any],
) -> dict[str, Any]:
    """The fields of a value with mean ``mean`` and standard deviation
    ``|mean| * rel_std``: ``value`` without spread (whatever the shared
    distribution); else ``mean`` and ``std`` (normal, by default, or
    lognormal), or the ``min`` and ``max`` of a uniform draw with that mean
    and standard deviation (mean ± sqrt(3) std). A project distribution gets
    ``mean`` and its ``arguments``; they are written for the others too, so
    that the checks refuse them (e.g. a misspelled ``rel_sd=0.1``)."""

    if rel_std == 0.0 and distribution in (None, *SHARED_DISTRIBUTIONS):
        return {"value": mean, **arguments}
    distribution = distribution or "normal"
    std = abs(mean * rel_std)
    if distribution == "uniform":
        half_width = np.sqrt(3.0) * std
        return {"distribution": distribution, "min": mean - half_width, "max": mean + half_width, **arguments}
    if distribution in ("normal", "lognormal"):
        return {"distribution": distribution, "mean": mean, "std": std, **arguments}
    return {"distribution": distribution, "mean": mean, **arguments}


def _bounds(drawn: dict[str, Any], lower_bound, upper_bound, bound_mode) -> dict[str, Any]:
    """The bounds of a drawn value; none for a fixed one, which is not drawn."""
    if "value" in drawn:
        return {}
    return {"lower_bound": lower_bound, "upper_bound": upper_bound, "bound_mode": bound_mode}


def zero_bound(mean: float, bound_mode: str) -> dict[str, Any]:
    """
    Bounds that keep a drawn weight's sign: ``lower_bound: 0`` for a weight
    with a mean of 0 or more, ``upper_bound: 0`` for a negative one, with
    ``bound_mode`` ``"redraw"`` or ``"clip"``. For :func:`weight`:
    ``weight(w, unit="pA", rel_std=0.1, **zero_bound(w, "redraw"))``.
    """
    if mean >= 0:
        return {"lower_bound": 0.0, "bound_mode": bound_mode}
    return {"upper_bound": 0.0, "bound_mode": bound_mode}


def weight(
    mean: float,
    *,
    unit: str,
    rel_std: float = 0.0,
    distribution: str | None = None,
    lower_bound: float | None = None,
    upper_bound: float | None = None,
    bound_mode: str | None = None,
    **arguments: float,
) -> dict[str, Any]:
    """
    A ``weight`` entry for a connection, background input or stimulus, from
    its mean and its relative spread, as papers and reference codes give them.

    Parameters
    ----------
    mean
        The mean weight the simulator gets, in ``unit``.
    unit
        ``"pA"`` (a current), ``"nS"`` (a conductance) or ``"mV"`` (a jump of
        the membrane potential). Nothing is converted.
    rel_std
        Standard deviation divided by ``|mean|``; 0 (and no ``distribution``)
        for a fixed weight, written as ``value``.
    distribution
        ``"normal"`` (the default with a spread) or ``"lognormal"``, written
        with ``mean`` and ``std = |mean| * rel_std``; ``"uniform"``, written as
        the ``min`` and ``max`` with that mean and standard deviation; or a
        project distribution (connections only), written with ``mean``.
    **arguments
        A project distribution's arguments, e.g. ``beta=20``.
    lower_bound, upper_bound, bound_mode
        Bounds of a drawn weight, and what to do past them (``"redraw"`` or
        ``"clip"``); see :func:`zero_bound` to keep the weight's sign. A fixed
        weight is not drawn, so it is written without them.

    Returns
    -------
    dict
        The entry as written in the YAML file. It is checked against
        :class:`~microcircuit_lab.config.connectivity.WeightDistribution`, so a bad value
        raises here.
    """
    drawn = _drawn(mean, rel_std, distribution, arguments)
    return WeightDistribution(
        **drawn, **_bounds(drawn, lower_bound, upper_bound, bound_mode), unit=unit
    ).model_dump(exclude_none=True)


def delay(
    mean: float,
    *,
    rel_std: float = 0.0,
    distribution: str | None = None,
    lower_bound: float | None = None,
    upper_bound: float | None = None,
    bound_mode: str | None = None,
    **arguments: float,
) -> dict[str, Any]:
    """
    A ``delay`` entry for a connection, background input or stimulus, as
    :func:`weight`.

    Parameters
    ----------
    mean
        Mean delay in ms.
    rel_std
        Standard deviation divided by ``mean``; 0 for a fixed delay.
    distribution, **arguments
        As in :func:`weight`.
    lower_bound, upper_bound, bound_mode
        Bounds (ms) of a drawn delay, which needs a ``lower_bound``, and what
        to do past them (``"redraw"`` or ``"clip"``); left out for a fixed delay.

    Returns
    -------
    dict
        The entry as written in the YAML file, checked against
        :class:`~microcircuit_lab.config.connectivity.DelayDistribution`.
    """
    drawn = _drawn(mean, rel_std, distribution, arguments)
    return DelayDistribution(**drawn, **_bounds(drawn, lower_bound, upper_bound, bound_mode)).model_dump(
        exclude_none=True
    )


def num_synapses_from_conn_prob(
    conn_prob: float,
    n_source: int,
    n_target: int,
) -> int:
    """
    Compute the total number of synapses from a connection probability.

    Parameters
    ----------
    conn_prob
        Connection probability.

    n_source
        Number of source neurons.

    n_target
        Number of target neurons.

    Returns
    -------
    int
        Expected total number of synapses.
    """

    if conn_prob <= 0.0:
        return 0

    prod = n_source * n_target

    num_syn = np.log(1.0 - conn_prob) / np.log((prod - 1.0) / prod)

    return int(round(num_syn))
