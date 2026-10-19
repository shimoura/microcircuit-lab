"""
NEST parameters for weights, delays and per-neuron values.

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


def create_weight_spec(weight, bound_mode: str):
    """
    Create a NEST weight parameter.

    A weight without spread (fixed, or ``rel_std`` 0) is returned as
    given. Every distribution has the given mean and standard deviation;
    a uniform one spans mean ± sqrt(3) * std. A lognormal weight has the
    sign of its mean. A normal or uniform weight of the other sign is
    redrawn or clipped to 0, as set by the network's ``bound_mode``.
    """

    if weight.distribution == "fixed" or weight.rel_std == 0.0:
        return weight.mean

    std = abs(weight.mean * weight.rel_std)

    if weight.distribution in ("normal", "uniform"):
        if weight.distribution == "normal":
            distribution = nest.random.normal(mean=weight.mean, std=std)
        else:
            half_width = np.sqrt(3.0) * std
            distribution = nest.random.uniform(
                min=weight.mean - half_width, max=weight.mean + half_width
            )
        clip = bound_mode == "clip"

        if weight.mean >= 0:
            if clip:
                return nest.math.max(distribution, 0.0)
            return nest.math.redraw(distribution, min=0.0, max=float("inf"))

        if clip:
            return nest.math.min(distribution, 0.0)
        return nest.math.redraw(distribution, min=-float("inf"), max=0.0)

    if weight.distribution == "lognormal":
        variance = (weight.mean * weight.rel_std) ** 2
        sigma2 = np.log(1.0 + variance / weight.mean**2)
        sigma = np.sqrt(sigma2)
        mu = np.log(abs(weight.mean)) - sigma2 / 2.0

        distribution = nest.random.lognormal(mean=mu, std=sigma)
        return distribution if weight.mean > 0 else -1.0 * distribution

    raise NotImplementedError(f"Unsupported distribution: {weight.distribution}")


def create_delay_parameter(delay, bound_mode: str):
    """
    Create a NEST delay parameter.

    A drawn delay below the minimum (``delay.minimum``, or half the
    simulation step if not set) is redrawn or clipped to the minimum,
    as set by the network's ``bound_mode``. The minimum is never below
    half the simulation step, which NEST would round to a delay of 0.
    A fixed delay is returned as given; a uniform one is drawn from
    mean ± sqrt(3) * std, which has that mean and standard deviation.
    """

    if delay.distribution == "fixed" or delay.rel_std == 0.0:
        return delay.mean

    std = delay.mean * delay.rel_std
    min_delay = 0.5 * nest.resolution
    if delay.minimum is not None:
        min_delay = max(delay.minimum, min_delay)

    if delay.distribution == "normal":
        distribution = nest.random.normal(mean=delay.mean, std=std)

    elif delay.distribution == "uniform":
        half_width = np.sqrt(3.0) * std
        distribution = nest.random.uniform(
            min=delay.mean - half_width, max=delay.mean + half_width
        )

    elif delay.distribution == "lognormal":
        variance = std**2
        sigma_squared = np.log1p(variance / delay.mean**2)
        sigma = np.sqrt(sigma_squared)
        mu = np.log(delay.mean) - 0.5 * sigma_squared

        distribution = nest.random.lognormal(mean=mu, std=sigma)

    else:
        raise ValueError(f"Unsupported delay distribution: {delay.distribution!r}")

    if bound_mode == "clip":
        return nest.math.max(distribution, min_delay)

    return nest.math.redraw(distribution, min=min_delay, max=float("inf"))
