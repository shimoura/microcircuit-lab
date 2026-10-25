"""
Weights, delays and per-neuron values drawn from their distributions in Brian2.

The shared distributions are the NEST backend's (``backends/nest/distributions.py``),
with the same means, standard deviations and bounds; a project's own are a
``Distribution`` (``models.py``), drawn from its expression. Weights and delays are
drawn by Brian2 from string expressions, so the values of millions of synapses
are never held in Python; per-neuron values are drawn with numpy. One
expression draws the values of many connections: their numbers are read from
lookup tables, by an index such as the connection's pair of populations, so
Brian2 generates one piece of code for all of them.
"""

from __future__ import annotations

import math
import re

import brian2 as b2
import numpy as np
from brian2.devices.device import RuntimeDevice

from microcircuit_lab.backends.brian2.connections import table
from microcircuit_lab.backends.brian2.models import Distribution
from microcircuit_lab.config.distributions import DrawnValue

#: The distributions a per-neuron value can have: NEST's names (nest.random)
#: and arguments, and how numpy draws them.
PER_NEURON_DRAWS = {
    "normal": (("mean", "std"), lambda rng, a, n: rng.normal(a["mean"], a["std"], n)),
    "uniform": (("min", "max"), lambda rng, a, n: rng.uniform(a["min"], a["max"], n)),
    "lognormal": (("mean", "std"), lambda rng, a, n: rng.lognormal(a["mean"], a["std"], n)),
    "exponential": (("beta",), lambda rng, a, n: rng.exponential(a["beta"], n)),
}

#: With bound_mode "redraw", values out of bounds are drawn again until fewer
#: than LEFT_OUT of them are expected (at most MAX_REDRAW_ROUNDS times); the
#: rest are clipped. Each round is one more piece of code for Brian2, so a
#: bound that is (almost) never crossed (fewer than NEVER expected) is not
#: checked at all.
LEFT_OUT = 1e-3
MAX_REDRAW_ROUNDS = 50
NEVER = 1e-9


def per_neuron_value(value, size: int, rng: np.random.Generator):
    """
    A number as given, or one value per neuron drawn from its distribution.
    """

    if not isinstance(value, DrawnValue):
        return value

    if value.distribution not in PER_NEURON_DRAWS:
        raise ValueError(
            f"The Brian2 backend has no distribution '{value.distribution}'; "
            f"it has {sorted(PER_NEURON_DRAWS)}."
        )
    arguments, draw = PER_NEURON_DRAWS[value.distribution]
    missing = [name for name in arguments if name not in value.model_extra]
    if missing:
        raise ValueError(f"Distribution '{value.distribution}' needs {missing}.")
    return draw(rng, value.model_extra, size)


#: How each kind of distribution is drawn from its two numbers a and b (and
#: the sign s of a lognormal value); a fixed value is a normal one with b = 0.
DRAWS = {
    "normal": "({a} + {b}*randn())",
    "uniform": "({a} + {b}*rand())",
    "lognormal": "{s}*exp({a} + {b}*randn())",
}


def _numbers(mean: float, rel_std: float, distribution: str) -> tuple[str, float, float, float]:
    """The kind of draw (see DRAWS) and its numbers a, b and s, for a value with
    mean ``mean`` and standard deviation ``|mean| * rel_std``. A uniform value
    spans mean ± sqrt(3) * std; a lognormal one has the sign of its mean."""

    if distribution == "fixed" or rel_std == 0.0:
        return "normal", mean, 0.0, 1.0
    std = abs(mean * rel_std)
    if distribution == "normal":
        return "normal", mean, std, 1.0
    if distribution == "uniform":
        half_width = np.sqrt(3.0) * std
        return "uniform", mean - half_width, 2 * half_width, 1.0
    if distribution == "lognormal":
        sigma2 = np.log1p((std / mean) ** 2)
        return "lognormal", np.log(abs(mean)) - sigma2 / 2.0, np.sqrt(sigma2), float(np.sign(mean))
    raise ValueError(f"Unsupported distribution: {distribution!r}")


def chance_below(bound: float, mean: float, rel_std: float, distribution: str) -> float:
    """The chance that a value drawn as by set_drawn is below ``bound``."""

    if distribution == "fixed" or rel_std == 0.0:
        return float(mean < bound)
    std = abs(mean * rel_std)
    if distribution == "normal":
        return 0.5 * math.erfc((mean - bound) / (std * math.sqrt(2.0)))
    if distribution == "uniform":
        half_width = np.sqrt(3.0) * std
        return min(max((bound - mean + half_width) / (2 * half_width), 0.0), 1.0)
    if distribution == "lognormal":
        if bound <= 0.0:
            return 0.0
        sigma2 = np.log1p(rel_std**2)
        mu = np.log(mean) - sigma2 / 2.0
        return 0.5 * math.erfc((mu - math.log(bound)) / math.sqrt(2.0 * sigma2))
    raise ValueError(f"Unsupported distribution: {distribution!r}")


def _project_expression(distribution: Distribution, mean: float, rel_std: float, parameters: dict) -> str:
    """A project distribution's expression with its ``mean``, ``rel_std`` and
    ``parameters`` written in as numbers, so the entries of one Synapses
    cannot mix up their values."""

    values = {"mean": mean, "rel_std": rel_std, **parameters}
    return re.sub(
        r"\b[A-Za-z_]\w*\b",
        lambda name: f"({values[name[0]]!r})" if name[0] in values else name[0],
        distribution.expression,
    )


def _set_projects(target, variable, index, entries, unit, bound_mode, wrong, bound, projects) -> None:
    """The values of the entries ``projects`` (``{k: (Distribution,
    parameters)}``), from each distribution's expression; past the bound,
    drawn again its ``redraw_rounds`` times (bound_mode "redraw"), then set to
    the bound. One assignment per entry: each has its own expression."""

    values = getattr(target, variable)
    for k, (distribution, parameters) in projects.items():
        mean, rel_std = entries[k][:2]
        expression = f"({_project_expression(distribution, mean, rel_std, parameters)})*{unit}"
        here = f"({index}) == {k}"
        values[here] = expression
        if wrong is None:
            continue
        rounds = distribution.redraw_rounds if bound_mode == "redraw" else 0
        for _ in range(rounds):
            values[f"{here} and {wrong}"] = expression
        values[f"{here} and {wrong}"] = bound


def set_drawn(
    target,
    variable: str,
    index: str,
    entries: dict[int, tuple[float, float, str]],
    unit: str,
    bound_mode: str,
    wrong: str | None = None,
    bound: str | None = None,
    out_of_bounds: list[tuple[int, float]] = (),
    projects: dict[int, tuple[Distribution, dict]] | None = None,
) -> None:
    """
    Set ``variable`` of a Brian2 group or synapses to values drawn for each
    entry ``{k: (mean, rel_std, distribution)}``, for the neurons or synapses
    whose ``index`` (a Brian2 expression) is k.

    Then the values where the condition ``wrong`` holds are drawn again
    (bound_mode "redraw", see LEFT_OUT) and the rest set to ``bound``.
    ``out_of_bounds`` gives, per entry, its number of values and the chance of
    each to be out of bounds. Brian2 does all this itself, also in C++
    standalone mode, where the values cannot be looked at before the run.

    The entries in ``projects`` (``{k: (Distribution, parameters)}``) are
    drawn from their project distribution instead (see _set_projects).
    """

    projects = projects or {}
    shared = {k: entry for k, entry in entries.items() if k not in projects}
    if shared:
        _set_shared(target, variable, index, shared, unit, bound_mode, wrong, bound, out_of_bounds)
    _set_projects(target, variable, index, entries, unit, bound_mode, wrong, bound, projects)


def _set_shared(target, variable, index, entries, unit, bound_mode, wrong, bound, out_of_bounds) -> None:
    """set_drawn for the entries of shared distributions."""

    size = max(entries) + 1
    kinds, a, b, s = np.zeros(size, dtype=int), np.zeros(size), np.zeros(size), np.ones(size)
    names = list(DRAWS)
    for k, (mean, rel_std, distribution) in entries.items():
        kind, a[k], b[k], s[k] = _numbers(mean, rel_std, distribution)
        kinds[k] = names.index(kind)
    target.namespace.update({
        f"{variable}_{name}": table(values, f"{target.name}_{variable}_{name}")
        for name, values in (("a", a), ("b", b), ("s", s), ("kind", kinds))
    })

    def read(name: str) -> str:
        return f"{variable}_{name}(({index})*second)"

    used = sorted(set(kinds[list(entries)]))
    parts = [DRAWS[names[kind]].format(a=read("a"), b=read("b"), s=read("s")) for kind in used]
    if len(parts) == 1:
        expression = f"{parts[0]}*{unit}"
    else:
        expression = "(" + " + ".join(
            f"int({read('kind')} == {kind})*{part}" for kind, part in zip(used, parts)
        ) + f")*{unit}"
    setattr(target, variable, expression)

    def expected(rounds: int) -> float:
        return sum(n * chance ** (rounds + 1) for n, chance in out_of_bounds)

    if wrong is None or expected(0) < NEVER:
        return
    values = getattr(target, variable)
    if bound_mode == "redraw":
        look = isinstance(b2.get_device(), RuntimeDevice)
        rounds = 0
        while expected(rounds) >= LEFT_OUT and rounds < MAX_REDRAW_ROUNDS:
            if look and len(values[wrong]) == 0:
                break
            values[wrong] = expression
            rounds += 1
    values[wrong] = bound


def set_weights(
    target,
    variable: str,
    index: str,
    entries: dict[int, tuple[float, float, str, int]],
    unit: str,
    bound_mode: str,
    projects: dict[int, tuple[Distribution, dict]] | None = None,
) -> None:
    """
    Draw the weights ``variable`` of ``target`` for each entry
    ``{k: (mean, rel_std, distribution, number of weights)}``, by ``index``
    (see set_drawn; ``projects`` too).

    A normal or uniform weight of the other sign than its mean is redrawn or
    clipped to 0, as set by the network's ``bound_mode``; as in NEST. So is a
    project distribution's (see _set_projects).
    """

    projects = projects or {}

    sign = np.zeros(max(entries) + 1)
    out_of_bounds = []
    for k, (mean, rel_std, distribution, number) in entries.items():
        sign[k] = 1.0 if mean >= 0 else -1.0
        # A lognormal weight always has the sign of its mean; normal and uniform
        # ones are symmetric, so the chance of the other sign is that of a
        # weight of mean |mean| below 0.
        if distribution != "lognormal" and k not in projects:
            out_of_bounds.append((number, chance_below(0.0, abs(mean), rel_std, distribution)))
    target.namespace[f"{variable}_sign"] = table(sign, f"{target.name}_{variable}_sign")
    set_drawn(
        target, variable, index, {k: entry[:3] for k, entry in entries.items()}, unit, bound_mode,
        wrong=f"{variable}*{variable}_sign(({index})*second) < 0*{unit}",
        bound=f"0*{unit}",
        out_of_bounds=out_of_bounds,
        projects=projects,
    )


def set_delays(
    synapses,
    index: str,
    entries: dict[int, tuple[float, float, str, float | None, int]],
    bound_mode: str,
    resolution: float,
    projects: dict[int, tuple[Distribution, dict]] | None = None,
) -> None:
    """
    Draw the delays of ``synapses`` for each entry
    ``{k: (mean, rel_std, distribution, minimum, number of delays)}``, by
    ``index`` (see set_drawn).

    A drawn delay below the minimum (``minimum``, or half the simulation
    step if not set; never below half the step) is redrawn or clipped to the
    minimum, as set by the network's ``bound_mode``. A fixed delay is used
    as given. As in NEST. ``projects``: see set_drawn.
    """

    projects = projects or {}
    minimum_delay = np.zeros(max(entries) + 1)
    out_of_bounds = []
    for k, (mean, rel_std, distribution, minimum, number) in entries.items():
        minimum_delay[k] = 0.5 * resolution
        # NaN is "not set" too
        if minimum is not None and minimum == minimum:
            minimum_delay[k] = max(minimum, minimum_delay[k])
        if distribution != "fixed" and rel_std != 0.0 and k not in projects:
            out_of_bounds.append((number, chance_below(minimum_delay[k], mean, rel_std, distribution)))
    synapses.namespace["delay_minimum"] = table(minimum_delay, f"{synapses.name}_delay_minimum")
    set_drawn(
        synapses, "delay", index, {k: entry[:3] for k, entry in entries.items()}, "ms", bound_mode,
        wrong=f"delay < delay_minimum(({index})*second)*ms",
        bound=f"delay_minimum(({index})*second)*ms",
        out_of_bounds=out_of_bounds,
        projects=projects,
    )
