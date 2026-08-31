"""
Builders for the ``weight`` / ``delay`` dicts a generator writes into
``connectivity.yaml`` and ``background_inputs.yaml``.

Optional sugar over :class:`~microcircuit_lab.config.network.WeightDistribution`
and :class:`~microcircuit_lab.config.network.DelayDistribution`: those stay
the single source of truth for the field names and the allowed ``unit`` /
``distribution`` values -- each helper just constructs one and dumps it, so
a bad value raises here rather than surfacing later, and a schema change is
picked up automatically instead of needing an edit in this file.

``distribution`` is inferred from ``rel_std`` when not given: no spread
means a single fixed value, otherwise ``normal``. Pass it explicitly for
anything else (e.g. ``"lognormal"``).
"""

from __future__ import annotations

from typing import Any

from microcircuit_lab.config.network import DelayDistribution, WeightDistribution


def _distribution(rel_std: float, explicit: str | None) -> str:
    if explicit is not None:
        return explicit
    return "fixed" if rel_std == 0.0 else "normal"


def weight(
    mean: float,
    *,
    unit: str,
    rel_std: float = 0.0,
    distribution: str | None = None,
) -> dict[str, Any]:
    """A connection or background weight.

    ``unit`` selects how ``mean`` is read -- ``"PSP"`` (mV, converted for
    the target neuron), ``"PSC"`` (pA, as given) or ``"native"`` (as given,
    no interpretation); ``WeightDistribution.unit`` is authoritative.
    """
    return WeightDistribution(
        mean=mean,
        rel_std=rel_std,
        unit=unit,
        distribution=_distribution(rel_std, distribution),
    ).model_dump()


def delay(
    mean: float,
    *,
    rel_std: float = 0.0,
    distribution: str | None = None,
) -> dict[str, Any]:
    """A connection or background delay, ``mean`` in ms."""
    return DelayDistribution(
        mean=mean,
        rel_std=rel_std,
        distribution=_distribution(rel_std, distribution),
    ).model_dump()
