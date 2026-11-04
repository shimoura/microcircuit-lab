"""
Weights, delays and per-neuron values drawn from their distributions in NEST.

A value given as a distribution becomes a NEST parameter that draws one value
per neuron or synapse; a fixed value is passed on as it is. A name is looked
up in this order: a shared distribution (normal, lognormal, uniform), NEST's
own (``nest.random``, e.g. ``exponential``), then a function of the project,
in a file of ``extensions/nest/`` (or a module given as ``extensions``) that
returns a NEST parameter:

    def erlang2(beta):
        return nest.random.exponential(beta=beta) + nest.random.exponential(beta=beta)

The function gets the keys of the entry it names (``{distribution: erlang2,
beta: 20, ...}``), as NEST's own do. A lognormal value's ``mean`` and ``std``
are those of the values (see ``config/connectivity.py``).
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable, Sequence
from pathlib import Path

import nest

from microcircuit_lab.config.connectivity import (
    SHARED_DISTRIBUTIONS,
    lognormal_parameters,
)
from microcircuit_lab.project_code import find_functions

EXTENSIONS_FOLDER = Path("extensions") / "nest"


def _nest_distributions() -> dict[str, Callable]:
    """NEST's own distributions, by name."""
    return {name: item for name, item in vars(nest.random).items() if inspect.isfunction(item)}


def load_functions(extensions: Sequence[str] = ()) -> dict[str, Callable]:
    """
    The project's distributions: every function in the files of
    ``extensions/nest/`` (of the folder you run from) and of the modules
    ``extensions`` (see :func:`microcircuit_lab.project_code.find_functions`).
    None may take a name that is shared or NEST's own.
    """

    found = find_functions(EXTENSIONS_FOLDER, "extensions.nest", extensions)
    taken = {**dict.fromkeys(SHARED_DISTRIBUTIONS, "a shared distribution"),
             **dict.fromkeys(_nest_distributions(), "NEST's own (nest.random)")}
    clashes = sorted(set(found) & set(taken))
    if clashes:
        raise ValueError(
            f"The project defines a function named {clashes[0]!r}, which is {taken[clashes[0]]}; "
            "give it another name."
        )
    return found


def lookup(name: str, functions: dict[str, Callable]) -> Callable:
    """The function that draws from the distribution ``name``: NEST's own
    or the project's (``functions``, see :func:`load_functions`)."""

    draw = _nest_distributions().get(name) or functions.get(name)
    if draw is None:
        raise ValueError(
            f"NEST has no distribution {name!r}: nest.random has {sorted(_nest_distributions())}, and "
            f"{EXTENSIONS_FOLDER}/ (or --extensions) defines {sorted(functions)}."
        )
    return draw


@functools.cache
def arguments(draw: Callable) -> tuple[str, ...]:
    """The names of the arguments a distribution's function takes, all of
    which the entry gives: a NEST default left out would not show in the
    files."""
    return tuple(inspect.signature(draw).parameters)


def drawn_parameter(fields: dict, functions: dict[str, Callable]):
    """
    A NEST value from the ``fields`` of a weight, delay or neuron value in
    the config files (``config/connectivity.py``; a number left out is None
    or NaN) and its arguments: a fixed ``value`` as it is, or a NEST
    parameter that draws one value per synapse or neuron from
    ``distribution``, within its bounds.

    ``mean`` and ``std`` are those of the drawn values: a lognormal value is
    drawn with the log-space numbers that give them, and has the sign of
    ``mean``. A value past ``lower_bound`` or ``upper_bound`` is drawn again
    (``bound_mode`` "redraw") or set to the bound ("clip").
    """

    distribution, mean = fields["distribution"], fields["mean"]
    if distribution is None:
        return fields["value"]
    if distribution == "normal":
        drawn = nest.random.normal(mean=mean, std=fields["std"])
    elif distribution == "uniform":
        drawn = nest.random.uniform(min=fields["min"], max=fields["max"])
    elif distribution == "lognormal":
        mu, sigma = lognormal_parameters(mean, fields["std"])
        drawn = nest.random.lognormal(mean=mu, std=sigma)
        if mean < 0:
            drawn = -1.0 * drawn
    else:
        draw = lookup(distribution, functions)
        drawn = draw(**{name: fields[name] for name in arguments(draw)})

    lower = None if _unset(fields["lower_bound"]) else fields["lower_bound"]
    upper = None if _unset(fields["upper_bound"]) else fields["upper_bound"]
    if fields["bound_mode"] == "clip":
        if lower is not None:
            drawn = nest.math.max(drawn, lower)
        if upper is not None:
            drawn = nest.math.min(drawn, upper)
        return drawn
    if fields["bound_mode"] == "redraw":
        low = -float("inf") if lower is None else lower
        high = float("inf") if upper is None else upper
        return nest.math.redraw(drawn, min=low, max=high)
    return drawn


def _unset(number) -> bool:
    return number is None or number != number
