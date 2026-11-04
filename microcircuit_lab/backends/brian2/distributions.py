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

import logging
import math
import re

import brian2 as b2
import numpy as np
from brian2.devices.device import RuntimeDevice

from microcircuit_lab.backends.brian2.connections import table
from microcircuit_lab.backends.brian2.models import Distribution
from microcircuit_lab.config.connectivity import DelayDistribution, lognormal_parameters

logger = logging.getLogger(__name__)

#: With bound_mode "redraw", values out of bounds are drawn again until fewer
#: than LEFT_OUT of them are expected (at most MAX_REDRAW_ROUNDS times); the
#: rest are clipped (with a warning if more are expected). Each round is one
#: more piece of code for Brian2, so a bound that is (almost) never crossed
#: (fewer than NEVER expected) is not checked at all.
LEFT_OUT = 1e-3
MAX_REDRAW_ROUNDS = 50
NEVER = 1e-9


def fixed(value: float) -> dict:
    """The fields of a fixed value, as set_drawn takes them."""
    return {name: None for name in DelayDistribution.model_fields} | {"value": value}


#: How each kind of distribution is drawn from its two numbers a and b (and
#: the sign s of a lognormal value); a fixed value is a normal one with b = 0.
DRAWS = {
    "normal": "({a} + {b}*randn())",
    "uniform": "({a} + {b}*rand())",
    "lognormal": "{s}*exp({a} + {b}*randn())",
}


def _unset(number) -> bool:
    return number is None or number != number


def _numbers(fields: dict) -> tuple[str, float, float, float]:
    """The kind of draw (see DRAWS) and its numbers a, b and s, from the fields
    of a weight or delay (config/connectivity.py): a uniform value spans min
    to max; a lognormal one has the mean and standard deviation of its fields,
    and the sign of its mean."""

    distribution = fields["distribution"]
    if distribution is None:
        return "normal", fields["value"], 0.0, 1.0
    if distribution == "normal":
        return "normal", fields["mean"], fields["std"], 1.0
    if distribution == "uniform":
        return "uniform", fields["min"], fields["max"] - fields["min"], 1.0
    if distribution == "lognormal":
        mu, sigma = lognormal_parameters(fields["mean"], fields["std"])
        return "lognormal", mu, sigma, float(np.sign(fields["mean"]))
    raise ValueError(f"Unsupported distribution: {distribution!r}")


def _chance_past(bound: float, fields: dict, below: bool) -> float:
    """The chance that a value drawn from ``fields`` is below ``bound``
    (``below``) or above it. Each direction is computed on its own, so a tiny
    chance is not lost to rounding (it decides how often to redraw)."""

    kind, a, b, s = _numbers(fields)
    if b == 0.0:
        value = s * math.exp(a) if kind == "lognormal" else a
        return float(value < bound if below else value > bound)
    if kind == "normal":
        z = (a - bound) / (b * math.sqrt(2.0))
        return 0.5 * math.erfc(z if below else -z)
    if kind == "uniform":
        share = min(max((bound - a) / b, 0.0), 1.0)
        return share if below else 1.0 - share
    # A lognormal value s * exp(x), x normal (a, b): mirror a negative one.
    if s < 0:
        bound, below = -bound, not below
    if bound <= 0.0:
        return 0.0 if below else 1.0
    z = (a - math.log(bound)) / (b * math.sqrt(2.0))
    return 0.5 * math.erfc(z if below else -z)


def chance_out_of_bounds(fields: dict) -> float:
    """The chance that a value drawn from ``fields`` is past its bounds."""
    chance = 0.0
    if not _unset(fields["lower_bound"]):
        chance += _chance_past(fields["lower_bound"], fields, below=True)
    if not _unset(fields["upper_bound"]):
        chance += _chance_past(fields["upper_bound"], fields, below=False)
    return chance


def negated(fields: dict) -> dict:
    """The fields of the negative of a value: e.g. an inhibitory weight onto a
    conductance, which Brian2 takes as a size, as NEST does."""

    def minus(name: str):
        return None if _unset(fields[name]) else -fields[name]

    return {
        **fields,
        "value": minus("value"), "mean": minus("mean"),
        "min": minus("max"), "max": minus("min"),
        "lower_bound": minus("upper_bound"), "upper_bound": minus("lower_bound"),
    }


def _project_expression(distribution: Distribution, fields: dict) -> str:
    """A project distribution's expression with the fields it was given
    (``mean``, ``std``, ...) and its arguments (any other number in
    ``fields``) written in as numbers, so the entries of one Synapses cannot
    mix up their values."""

    text = ("distribution", "lower_bound", "upper_bound", "bound_mode", "unit")
    values = {name: value for name, value in fields.items() if name not in text and not _unset(value)}
    return re.sub(
        r"\b[A-Za-z_]\w*\b",
        lambda name: f"({values[name[0]]!r})" if name[0] in values else name[0],
        distribution.expression,
    )


def set_drawn(
    target,
    variable: str,
    index: str,
    entries: dict[int, tuple[dict, int]],
    unit: str,
    projects: dict[int, Distribution] | None = None,
) -> None:
    """
    Set ``variable`` of a Brian2 group or synapses to values drawn for each
    entry ``{k: (fields, number of values)}`` (the fields of a weight or
    delay, see config/connectivity.py), for the neurons or synapses whose
    ``index`` (a Brian2 expression) is k. The entries in ``projects`` (``{k:
    Distribution}``) are drawn from their project distribution instead.

    Then the values past their bounds are drawn again (``bound_mode``
    "redraw"; see LEFT_OUT, or the distribution's ``redraw_rounds``) and the
    rest set to the bound. Brian2 does all this itself, also in C++ standalone
    mode, where the values cannot be looked at before the run.
    """

    projects = projects or {}
    size = max(entries) + 1
    lower, upper, redraw = np.full(size, -np.inf), np.full(size, np.inf), np.zeros(size)
    for k, (fields, _) in entries.items():
        if not _unset(fields["lower_bound"]):
            lower[k] = fields["lower_bound"]
        if not _unset(fields["upper_bound"]):
            upper[k] = fields["upper_bound"]
        redraw[k] = fields["bound_mode"] == "redraw"
    target.namespace.update({
        f"{variable}_{name}": table(values, f"{target.name}_{variable}_{name}")
        for name, values in (("lower", lower), ("upper", upper), ("redraw", redraw))
    })

    def read(name: str) -> str:
        return f"{variable}_{name}(({index})*second)"

    # Past a bound: only the comparisons some entry needs.
    past = [f"{variable} < {read('lower')}*{unit}"] * bool(np.isfinite(lower).any())
    past += [f"{variable} > {read('upper')}*{unit}"] * bool(np.isfinite(upper).any())
    wrong = " or ".join(past) or None
    if wrong is not None and len(past) == 2:
        wrong = f"({wrong})"
    to_redraw = wrong if redraw.all() else f"{wrong} and {read('redraw')} == 1"

    clip = f"clip({variable}, {read('lower')}*{unit}, {read('upper')}*{unit})"
    shared = {k: entry for k, entry in entries.items() if k not in projects}
    if shared:
        _set_shared(target, variable, read, shared, unit, wrong, to_redraw, clip)
    _set_projects(target, variable, index, entries, unit, wrong, projects, clip)


def _set_projects(target, variable, index, entries, unit, wrong, projects, clip) -> None:
    """The values of the entries ``projects`` (``{k: Distribution}``), from
    each distribution's expression; past a bound, drawn again its
    ``redraw_rounds`` times (``bound_mode`` "redraw"), then set to the bound
    (``clip``). One assignment per entry: each has its own expression."""

    values = getattr(target, variable)
    for k, distribution in projects.items():
        fields = entries[k][0]
        expression = f"({_project_expression(distribution, fields)})*{unit}"
        here = f"({index}) == {k}"
        values[here] = expression
        if wrong is None:
            continue
        rounds = distribution.redraw_rounds if fields["bound_mode"] == "redraw" else 0
        for _ in range(rounds):
            values[f"{here} and {wrong}"] = expression
        values[f"{here} and {wrong}"] = clip


def _set_shared(target, variable, read, entries, unit, wrong, to_redraw, clip) -> None:
    """set_drawn for the entries of shared distributions and fixed values. A
    bound that is (almost) never crossed (fewer than NEVER values expected
    past it) is not checked at all: each check is one more piece of code for
    Brian2."""

    size = max(entries) + 1
    kinds, a, b, s = np.zeros(size, dtype=int), np.zeros(size), np.zeros(size), np.ones(size)
    names = list(DRAWS)
    for k, (fields, _) in entries.items():
        kind, a[k], b[k], s[k] = _numbers(fields)
        kinds[k] = names.index(kind)
    target.namespace.update({
        f"{variable}_{name}": table(values, f"{target.name}_{variable}_{name}")
        for name, values in (("a", a), ("b", b), ("s", s), ("kind", kinds))
    })

    def expression(kinds_here: list[int]) -> str:
        parts = [DRAWS[names[kind]].format(a=read("a"), b=read("b"), s=read("s")) for kind in kinds_here]
        if len(parts) == 1:
            return f"{parts[0]}*{unit}"
        return "(" + " + ".join(
            f"int({read('kind')} == {kind})*{part}" for kind, part in zip(kinds_here, parts)
        ) + f")*{unit}"

    # One expression for all kinds, except lognormal next to another kind: it
    # gets its own assignment, since Brian2 allows one randn() per expression
    # and exp() of another kind's numbers could overflow (0*inf is NaN).
    used = sorted(set(kinds[list(entries)]))
    lognormal = names.index("lognormal")
    others = [kind for kind in used if kind != lognormal]
    if lognormal in used and others:
        assignments = [
            (f"{read('kind')} != {lognormal}", expression(others)),
            (f"{read('kind')} == {lognormal}", expression([lognormal])),
        ]
    else:
        assignments = [(None, expression(used))]
    values = getattr(target, variable)
    for condition, drawn in assignments:
        if condition is None:
            setattr(target, variable, drawn)
        else:
            values[condition] = drawn

    # How many values are expected past their bounds after some rounds of
    # redrawing (only the entries that redraw are drawn again).
    out = [(number, chance_out_of_bounds(fields), fields["bound_mode"] == "redraw")
           for fields, number in entries.values()]

    def expected(rounds: int) -> float:
        return sum(n * chance ** (rounds + 1 if again else 1) for n, chance, again in out)

    if wrong is None or expected(0) < NEVER:
        return
    look = isinstance(b2.get_device(), RuntimeDevice)
    rounds = 0
    while any(again for *_, again in out) and expected(rounds) >= LEFT_OUT and rounds < MAX_REDRAW_ROUNDS:
        if look and len(values[to_redraw]) == 0:
            break
        for condition, drawn in assignments:
            values[to_redraw if condition is None else f"({to_redraw}) and {condition}"] = drawn
        rounds += 1
    if rounds == MAX_REDRAW_ROUNDS:
        # In C++ standalone mode the values are known only when it runs.
        left = len(values[to_redraw]) if look else expected(rounds)
        if left >= LEFT_OUT:
            logger.warning(
                "%s of %s: about %d values are still out of bounds after %d redraws and are set "
                "to the bound; their distribution lies mostly past it.",
                variable, target.name, math.ceil(left), MAX_REDRAW_ROUNDS,
            )
    values[wrong] = clip
