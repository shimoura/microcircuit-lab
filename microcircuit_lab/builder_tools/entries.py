"""
The ``weight`` and ``delay`` entries of a connection, background input or
stimulus, and the number of synapses from a connection probability.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from microcircuit_lab.config.connectivity import DelayDistribution, WeightDistribution


def _distribution(rel_std: float, explicit: str | None) -> str:
    """The distribution to write: ``explicit`` if given, else ``fixed`` for
    no spread (``rel_std == 0``) and ``normal`` otherwise."""
    if explicit is not None:
        return explicit
    return "fixed" if rel_std == 0.0 else "normal"


def weight(
    mean: float,
    *,
    unit: str,
    rel_std: float = 0.0,
    distribution: str | None = None,
    parameters: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    A ``weight`` entry for a connection, background input or stimulus.

    Parameters
    ----------
    mean
        The weight the simulator gets, in ``unit``.
    unit
        ``"pA"`` (a current), ``"nS"`` (a conductance) or ``"mV"`` (a jump of
        the membrane potential). Nothing is converted.
    rel_std
        Standard deviation divided by ``|mean|``; 0 for a fixed weight.
    distribution
        ``"fixed"``, ``"normal"``, ``"uniform"`` or ``"lognormal"``, or a project
        distribution (connections only). By default ``fixed`` when ``rel_std`` is 0
        and ``normal`` otherwise.
    parameters
        A project distribution's parameters.

    Returns
    -------
    dict
        The entry as written in the YAML file. It is checked against
        :class:`~microcircuit_lab.config.connectivity.WeightDistribution`, so a bad value
        raises here.
    """
    return WeightDistribution(
        mean=mean,
        rel_std=rel_std,
        unit=unit,
        distribution=_distribution(rel_std, distribution),
        parameters=parameters,
    ).model_dump(exclude_none=True)


def delay(
    mean: float,
    *,
    rel_std: float = 0.0,
    distribution: str | None = None,
    minimum: float | None = None,
    parameters: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    A ``delay`` entry for a connection, background input or stimulus.

    Parameters
    ----------
    mean
        Mean delay in ms.
    rel_std
        Standard deviation divided by ``mean``; 0 for a fixed delay.
    distribution
        As in :func:`weight`.
    minimum
        Smallest allowed delay in ms; left out of the file when not given (the
        default is then half the simulation step).
    parameters
        A project distribution's parameters.

    Returns
    -------
    dict
        The entry as written in the YAML file, checked against
        :class:`~microcircuit_lab.config.connectivity.DelayDistribution`.
    """
    return DelayDistribution(
        mean=mean,
        rel_std=rel_std,
        distribution=_distribution(rel_std, distribution),
        minimum=minimum,
        parameters=parameters,
    ).model_dump(exclude_none=True)


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
