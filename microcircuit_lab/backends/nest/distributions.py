"""
Weights, delays and per-neuron values drawn from their distributions in NEST.

A value given as a distribution becomes a NEST parameter that draws one value
per neuron or synapse; a plain number is passed on as it is.
"""

from __future__ import annotations

import inspect

import nest
import numpy as np

from microcircuit_lab.config.distributions import DrawnValue


def per_neuron_value(value):
    """
    A number as given, or a NEST parameter drawing one value per neuron.
    """

    if not isinstance(value, DrawnValue):
        return value

    draw = getattr(nest.random, value.distribution, None)
    if not inspect.isfunction(draw):
        available = [name for name, item in vars(nest.random).items() if inspect.isfunction(item)]
        raise ValueError(
            f"NEST has no distribution '{value.distribution}'; nest.random has {available}."
        )
    # NEST would fill in a left-out argument with its default.
    missing = [name for name in inspect.signature(draw).parameters if name not in value.model_extra]
    if missing:
        raise ValueError(f"Distribution '{value.distribution}' needs {missing}.")
    return draw(**value.model_extra)


def create_weight_spec(mean: float, rel_std: float, distribution: str, bound_mode: str):
    """
    Create a NEST weight parameter from a weight's ``mean``, ``rel_std`` and
    ``distribution`` (the fields of a weight in the config files).

    A weight without spread (fixed, or ``rel_std`` 0) is returned as
    given. Every distribution has the given mean and standard deviation;
    a uniform one spans mean ± sqrt(3) * std. A lognormal weight has the
    sign of its mean. A normal or uniform weight of the other sign is
    redrawn or clipped to 0, as set by the network's ``bound_mode``.
    """

    if distribution == "fixed" or rel_std == 0.0:
        return mean

    std = abs(mean * rel_std)

    if distribution in ("normal", "uniform"):
        if distribution == "normal":
            drawn = nest.random.normal(mean=mean, std=std)
        else:
            half_width = np.sqrt(3.0) * std
            drawn = nest.random.uniform(
                min=mean - half_width, max=mean + half_width
            )
        clip = bound_mode == "clip"

        if mean >= 0:
            if clip:
                return nest.math.max(drawn, 0.0)
            return nest.math.redraw(drawn, min=0.0, max=float("inf"))

        if clip:
            return nest.math.min(drawn, 0.0)
        return nest.math.redraw(drawn, min=-float("inf"), max=0.0)

    if distribution == "lognormal":
        variance = (mean * rel_std) ** 2
        sigma2 = np.log(1.0 + variance / mean**2)
        sigma = np.sqrt(sigma2)
        mu = np.log(abs(mean)) - sigma2 / 2.0

        drawn = nest.random.lognormal(mean=mu, std=sigma)
        return drawn if mean > 0 else -1.0 * drawn

    raise NotImplementedError(f"Unsupported distribution: {distribution}")


def create_delay_parameter(
    mean: float,
    rel_std: float,
    distribution: str,
    minimum: float | None,
    bound_mode: str,
    resolution: float | None = None,
):
    """
    Create a NEST delay parameter from a delay's ``mean``, ``rel_std``,
    ``distribution`` and ``minimum`` (the fields of a delay in the config
    files; a ``minimum`` of None or NaN is not set).

    A drawn delay below the minimum (``minimum``, or half the
    simulation step if not set) is redrawn or clipped to the minimum,
    as set by the network's ``bound_mode``. The minimum is never below
    half the simulation step, which NEST would round to a delay of 0.
    A fixed delay is returned as given; a uniform one is drawn from
    mean ± sqrt(3) * std, which has that mean and standard deviation.

    ``resolution`` is the simulation step (ms); give it when creating many
    delays, since reading ``nest.resolution`` asks NEST for its whole status
    each time.
    """

    if distribution == "fixed" or rel_std == 0.0:
        return mean

    std = mean * rel_std
    min_delay = 0.5 * (nest.resolution if resolution is None else resolution)
    if minimum is not None and minimum == minimum:  # NaN is "not set" too
        min_delay = max(minimum, min_delay)

    if distribution == "normal":
        drawn = nest.random.normal(mean=mean, std=std)

    elif distribution == "uniform":
        half_width = np.sqrt(3.0) * std
        drawn = nest.random.uniform(
            min=mean - half_width, max=mean + half_width
        )

    elif distribution == "lognormal":
        variance = std**2
        sigma_squared = np.log1p(variance / mean**2)
        sigma = np.sqrt(sigma_squared)
        mu = np.log(mean) - 0.5 * sigma_squared

        drawn = nest.random.lognormal(mean=mu, std=sigma)

    else:
        raise ValueError(f"Unsupported delay distribution: {distribution!r}")

    if bound_mode == "clip":
        return nest.math.max(drawn, min_delay)

    return nest.math.redraw(drawn, min=min_delay, max=float("inf"))
