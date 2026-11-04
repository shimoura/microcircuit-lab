"""What ``connectivity.yaml`` may contain: one row per projection.

``WeightDistribution`` and ``DelayDistribution`` are also used by background
inputs and stimuli.
"""

from __future__ import annotations

import math
import typing
from typing import Annotated, Any, Literal

import numpy as np
from pydantic import (
    BeforeValidator,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    model_validator,
)

from microcircuit_lab.config.frozen_config import FrozenConfig

#: The distributions every backend draws weights and delays from, and the
#: fields each one takes: the mean and standard deviation of the drawn values,
#: or the range of a uniform draw. Any other name is a project distribution,
#: which the backend defines (see its ``models.py``), with its arguments as
#: keys of their own. A weight has the same fields as a delay
#: (DelayDistribution), and its unit.
SHARED_DISTRIBUTIONS = {"normal": ("mean", "std"), "lognormal": ("mean", "std"), "uniform": ("min", "max")}

#: What to do with a drawn weight or delay outside its bounds.
BoundMode = Literal["redraw", "clip"]

#: The arguments of a rule or distribution that is not shared, each a key of
#: its own next to the fields (``{rule: pairwise_poisson, pairs_avg_num: 0.3}``).
Arguments = dict[str, StrictInt | StrictFloat]


#: The weight units of earlier versions, and what to write instead.
OLD_UNITS = {
    "PSP": "unit: PSP was removed, so that the files show the weight the simulator gets: convert the "
    "PSP in the builder (e.g. builder_tools.psp_to_psc_iaf_psc_exp) and write unit: pA",
    "PSC": "unit: PSC is now written unit: pA",
    "native": "unit: native was removed: write the weight's unit, pA, nS or mV",
}

def old_field_message(name: str) -> str | None:
    """What to write instead of a field of a connection, weight or delay of
    earlier versions (``rel_std``, ``minimum``, ``parameters``); None for any
    other name."""
    if name == "rel_std":
        return (
            "rel_std was removed: write the standard deviation of the drawn values, std = |mean| x "
            "rel_std (e.g. {distribution: normal, mean: 87.8, std: 8.78}); a uniform value takes its "
            "range, min and max"
        )
    if name == "minimum":
        return "minimum was removed: write lower_bound with bound_mode (e.g. lower_bound: 0.1, bound_mode: redraw)"
    if name == "parameters":
        return (
            "parameters was removed: write each argument as a key of its own, next to the rule or "
            "distribution (e.g. {rule: pairwise_poisson, pairs_avg_num: 0.3} or {distribution: erlang2, "
            "beta: 20, mean: -40, unit: pA}); in a CSV file, one column per argument (pairs_avg_num, weight.beta)"
        )
    return None


def is_number_field(name: str) -> bool:
    """Whether a field of a weight or delay is a number (``value``, ``mean``,
    ..., the bounds), rather than text. The numbers are all in the weight's
    unit or in ms, so scaling a weight scales them all."""
    return float in typing.get_args(DelayDistribution.model_fields[name].annotation)


def _refuse_old_unit(unit):
    if isinstance(unit, str) and unit in OLD_UNITS:
        raise ValueError(OLD_UNITS[unit])
    return unit


def _given(values: np.ndarray) -> np.ndarray:
    """Where a column of a weight's or delay's field is set (not NaN, not None)."""
    if values.dtype == object:
        return np.array([value is not None for value in values], dtype=bool)
    return ~np.isnan(values)


def drawn_value_problems(fields: dict[str, np.ndarray], delay: bool) -> list[tuple[str, np.ndarray, str]]:
    """
    Where the fields of weights or delays do not fit together, as ``(field,
    rows, message)``, ``rows`` a boolean array.

    ``fields`` holds each field (``distribution``, ``value``, ``mean``, ...,
    ``bound_mode``) and each argument of a project distribution as an array
    with one entry per weight or delay, so the same checks serve one entry of
    a file and the millions of rows of a connection table. A field's own
    limits (e.g. ``std`` >= 0) are checked by pydantic with its ``Field``.
    """

    distribution = fields["distribution"]
    arguments = [name for name in fields if name not in DelayDistribution.model_fields]
    given = {name: _given(values) for name, values in fields.items()}
    fixed = ~given["distribution"]
    kinds = {name: distribution == name for name in SHARED_DISTRIBUTIONS}
    bounded = given["lower_bound"] | given["upper_bound"]
    with np.errstate(invalid="ignore"):
        checks = [
            ("distribution", distribution == "fixed",
             "fixed was removed: write a fixed value as value: (e.g. {value: 87.8})"),
            ("value", fixed & ~given["value"], "a fixed value needs value; a drawn one, a distribution"),
            ("value", ~fixed & given["value"], "value is a fixed value: with a distribution, remove it"),
            ("lower_bound", fixed & bounded, "a fixed value is not drawn: remove its bounds"),
            ("bound_mode", bounded & ~given["bound_mode"],
             "a bound needs bound_mode: redraw (draw again) or clip (set to the bound)"),
            ("bound_mode", ~bounded & given["bound_mode"], "bound_mode needs lower_bound or upper_bound"),
            ("upper_bound", fields["lower_bound"] > fields["upper_bound"], "lower_bound is above upper_bound"),
            ("max", kinds["uniform"] & (fields["min"] > fields["max"]), "min is above max"),
            ("mean", kinds["lognormal"] & (fields["mean"] == 0), "a lognormal value needs a mean other than 0"),
        ]
        for name, takes in SHARED_DISTRIBUTIONS.items():
            for field in takes:
                checks.append((field, kinds[name] & ~given[field], f"{name} needs {' and '.join(takes)}"))
            for field in ("mean", "std", "min", "max", *arguments):
                if field not in takes:
                    checks.append((field, kinds[name] & given[field], f"{name} takes {' and '.join(takes)}, not {field}"))
        for field in ("mean", "std", "min", "max", *arguments):
            checks.append((field, fixed & given[field], f"a fixed value takes value, not {field}"))
        if not delay:
            project = ~fixed & ~np.logical_or.reduce(list(kinds.values()))
            checks.append(("mean", project & ~given["mean"],
                           "a weight from a project distribution needs mean: its sign tells an excitatory "
                           "weight from an inhibitory one, and its expression can use it"))
        if delay:
            checks += [
                ("lower_bound", ~fixed & ~given["lower_bound"],
                 "a drawn delay needs lower_bound (ms), e.g. the simulation step, with bound_mode"),
                ("value", fixed & (fields["value"] <= 0), "a delay must be greater than 0"),
                ("mean", (kinds["normal"] | kinds["lognormal"]) & (fields["mean"] <= 0),
                 "a delay's mean must be greater than 0"),
            ]
    return [(field, rows, message) for field, rows, message in checks if rows.any()]


class _DrawnValue(FrozenConfig):
    """
    What weights and delays share: a fixed ``value``, or a ``distribution``
    to draw each one from, with the fields it takes; and optional bounds.
    The fields are declared by each (their units and examples differ); the
    checks are here.

    ``mean`` and ``std`` are those of the drawn values, for every
    distribution: a lognormal value with mean -351.2 and std 35.1 has that
    mean and standard deviation (and the sign of its mean); the backend
    finds the log-space numbers it draws with.
    """

    # To add a shared distribution: list it in SHARED_DISTRIBUTIONS and draw it
    # in backends/nest/distributions.py and backends/brian2/distributions.py.

    # Any other key is an argument of a project distribution.
    model_config = ConfigDict(frozen=True, extra="allow")
    __pydantic_extra__: Arguments = Field(init=False)

    @model_validator(mode="before")
    @classmethod
    def _refuse_old_fields(cls, data):
        old = [old_field_message(name) for name in data if old_field_message(name)] if isinstance(data, dict) else []
        if old:
            raise ValueError("; ".join(old))
        return data

    def _as_columns(self) -> dict[str, np.ndarray]:
        """The fields and arguments as columns of one row, as a connection
        table holds them."""
        columns = {
            name: np.array([getattr(self, name)], dtype=float if is_number_field(name) else object)
            for name in DelayDistribution.model_fields
        }
        return columns | {name: np.array([value], dtype=float) for name, value in self.model_extra.items()}

    @model_validator(mode="after")
    def _check_fields_fit(self):
        for field, _, message in drawn_value_problems(self._as_columns(), delay=isinstance(self, DelayDistribution)):
            raise ValueError(f"{field}: {message}")
        return self

    @property
    def expected(self) -> float:
        """The mean of the values, before any bound: ``value``, ``mean``, or
        the middle of ``min`` and ``max``. NaN for a project distribution
        without a ``mean``."""
        return expected_value({name: getattr(self, name) for name in DelayDistribution.model_fields})




def lognormal_parameters(mean: float, std: float) -> tuple[float, float]:
    """
    The ``mu`` and ``sigma`` of the normal distribution whose exponential
    has the mean ``|mean|`` and the standard deviation ``std``, which
    simulators draw a lognormal value with; the value then takes the sign of
    ``mean``.
    """
    sigma_squared = np.log1p(std**2 / mean**2)
    return np.log(abs(mean)) - 0.5 * sigma_squared, np.sqrt(sigma_squared)


def project_rows(distribution: np.ndarray) -> np.ndarray:
    """Where a column of distribution names holds a project distribution: a
    name that is not a shared one (``None`` is a fixed value)."""
    shared = np.logical_or.reduce([distribution == name for name in SHARED_DISTRIBUTIONS])
    return _given(distribution) & ~shared


def expected_values(fields: dict[str, np.ndarray]) -> np.ndarray:
    """
    The mean of each weight or delay before any bound, from the arrays of
    its fields (see :func:`drawn_value_problems`): ``value`` for a fixed one,
    the middle of ``min`` and ``max`` for a uniform one, else ``mean`` (NaN
    for a project distribution that has none).
    """

    distribution = fields["distribution"]
    fixed = ~_given(distribution)
    middle = (fields["min"] + fields["max"]) / 2
    return np.where(fixed, fields["value"], np.where(distribution == "uniform", middle, fields["mean"]))


def expected_value(fields: dict[str, Any]) -> float:
    """:func:`expected_values` of one weight or delay, from its fields (a
    number left out is None or NaN)."""
    return float(expected_values({
        name: np.array([fields[name]], dtype=float if is_number_field(name) else object)
        for name in ("distribution", "value", "mean", "min", "max")
    })[0])


class WeightDistribution(_DrawnValue):
    """
    The weight of each synapse: a fixed ``value``, or drawn from a
    ``distribution``, in ``unit``: ``pA`` (a current), ``nS`` (a conductance)
    or ``mV`` (a jump of the membrane potential). The core converts nothing
    with it; it is required, so the files say what each number is. Only
    current weights (``pA``) are in the scaling's compensation, whose mean
    current needs them. A negative weight is inhibitory.
    """

    distribution: str | None = Field(
        default=None,
        examples=["normal"],
        description="how each weight is drawn: normal or lognormal, with mean and std; uniform, "
        "with min and max; or the name of a project distribution, which the backend defines, "
        "with its arguments as keys of their own (e.g. beta: 20). Omit it for a fixed weight",
    )
    value: float | None = Field(default=None, description="a fixed weight, the same for every synapse")
    mean: float | None = Field(
        default=None, examples=[87.8], description="mean of the drawn weights (normal, lognormal); "
        "a negative weight is inhibitory"
    )
    std: float | None = Field(
        default=None, ge=0.0, examples=[8.78], description="standard deviation of the drawn weights (normal, lognormal)"
    )
    min: float | None = Field(default=None, description="smallest weight a uniform draw gives")
    max: float | None = Field(default=None, description="largest weight a uniform draw gives")
    lower_bound: float | None = Field(
        default=None, examples=[0.0],
        description="smallest allowed drawn weight (e.g. 0, so that an excitatory weight stays positive); "
        "omit for none",
    )
    upper_bound: float | None = Field(
        default=None, description="largest allowed drawn weight (e.g. 0 for an inhibitory one); omit for none"
    )
    bound_mode: BoundMode | None = Field(
        default=None, examples=["redraw"],
        description="with a bound: what to do with a drawn weight past it: redraw draws it again, clip "
        "sets it to the bound",
    )

    unit: Annotated[Literal["pA", "nS", "mV"], BeforeValidator(_refuse_old_unit)] = Field(
        examples=["pA"],
        description="the unit of the weight: pA (a current), nS (a conductance) or mV (a jump of the "
        "membrane potential); nothing is converted",
    )


class DelayDistribution(_DrawnValue):
    """The delay (ms) of each synapse: a fixed ``value``, or drawn from a
    ``distribution``, with a ``lower_bound``."""

    distribution: str | None = Field(
        default=None,
        examples=["normal"],
        description="how each delay is drawn: normal or lognormal, with mean and std; uniform, with "
        "min and max; or the name of a project distribution, with its arguments as keys of their own. "
        "Omit it for a fixed delay",
    )
    value: float | None = Field(default=None, description="a fixed delay (ms), the same for every synapse")
    mean: float | None = Field(default=None, examples=[1.5], description="mean of the drawn delays (ms)")
    std: float | None = Field(
        default=None, ge=0.0, examples=[0.75], description="standard deviation of the drawn delays (ms)"
    )
    min: float | None = Field(default=None, description="shortest delay (ms) a uniform draw gives")
    max: float | None = Field(default=None, description="longest delay (ms) a uniform draw gives")
    lower_bound: float | None = Field(
        default=None, examples=[0.1],
        description="shortest allowed drawn delay (ms), needed for a drawn delay; e.g. the simulation "
        "step (a delay below half a step rounds to 0)",
    )
    upper_bound: float | None = Field(default=None, description="longest allowed drawn delay (ms); omit for none")
    bound_mode: BoundMode | None = Field(
        default=None, examples=["redraw"],
        description="what to do with a drawn delay past a bound: redraw draws it again, clip sets it to the bound",
    )


# The field holding the number each connection rule takes.
RULE_NUMBER = {
    "fixed_total_number": "n_synapses",
    "fixed_indegree": "indegree",
    "fixed_outdegree": "outdegree",
    "pairwise_bernoulli": "p",
}

#: The rules every backend implements. Any other name is looked up by the
#: backend: a rule of the simulator or of the project.
SHARED_RULES = (*RULE_NUMBER, "one_to_one", "all_to_all")


class ConnectionConfig(FrozenConfig):
    """
    Description of one projection between two populations.

    ``rule`` says how the synapses are placed. Four rules take one number:

    - ``fixed_total_number``: ``n_synapses`` synapses in total;
    - ``fixed_indegree``: ``indegree`` synapses onto each target neuron;
    - ``fixed_outdegree``: ``outdegree`` synapses from each source neuron;
    - ``pairwise_bernoulli``: each source-target pair connected with
      probability ``p``.

    Two take none: ``one_to_one`` (the k-th source neuron to the k-th target
    neuron; the populations have the same size) and ``all_to_all``. Any other
    name is looked up by the backend (see ``SHARED_RULES``) and takes its
    arguments as keys of their own instead of a number
    (``{rule: pairwise_poisson, pairs_avg_num: 0.3}``). Any rule passes such
    keys to the simulator, which checks them.

    The core computes with the expected number of synapses
    (``builder_tools.mean_input.expected_synapses``), and ``scale_network`` scales
    the given number (``builder_tools.scaling.scale_rule_number``). Any other rule
    cannot be scaled yet.
    """

    # Any other key is an argument of the rule.
    model_config = ConfigDict(frozen=True, extra="allow")
    __pydantic_extra__: Arguments = Field(init=False)

    source: str = Field(examples=["L4_E"], description="source population name")
    target: str = Field(examples=["L23_E"], description="target population name")
    rule: str = Field(
        default="fixed_total_number",
        description="how the synapses are placed: fixed_total_number, fixed_indegree, "
        "fixed_outdegree or pairwise_bernoulli, each with its own number (n_synapses, indegree, "
        "outdegree or p); one_to_one or all_to_all, with no number; or another rule, which the "
        "simulator looks up, with its arguments as keys of their own (e.g. pairs_avg_num: 0.3)",
    )
    n_synapses: int | None = Field(
        default=None,
        ge=0,
        examples=[1440000],
        description="fixed_total_number: total number of synapses in the projection",
    )
    indegree: int | None = Field(
        default=None, ge=0, description="fixed_indegree: synapses onto each target neuron"
    )
    outdegree: int | None = Field(
        default=None, ge=0, description="fixed_outdegree: synapses from each source neuron"
    )
    p: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="pairwise_bernoulli: probability that a source-target pair is connected",
    )
    allow_autapses: bool | None = Field(
        default=None,
        description="whether a neuron may connect to itself; omit for the simulator's default",
    )
    allow_multapses: bool | None = Field(
        default=None,
        description="whether a pair may have several synapses; omit for the simulator's default",
    )
    synapse: str | None = Field(
        default=None,
        examples=["depressing"],
        description="name of an entry in synapses.yaml; omit for the default synapse",
    )
    weight: WeightDistribution = Field(description="weight of each synapse")
    delay: DelayDistribution = Field(description="delay of each synapse")

    @model_validator(mode="before")
    @classmethod
    def _refuse_parameters(cls, data):
        if isinstance(data, dict) and "parameters" in data:
            raise ValueError(old_field_message("parameters"))
        return data

    @model_validator(mode="after")
    def _check_number_matches_rule(self) -> ConnectionConfig:
        needed = RULE_NUMBER.get(self.rule)
        others = [
            name for name in RULE_NUMBER.values() if name != needed and getattr(self, name) is not None
        ]
        if needed is not None and (getattr(self, needed) is None or others):
            raise ValueError(
                f"rule {self.rule!r} takes the number {needed!r} and no other"
                + (f"; remove {others}" if others else "")
            )
        if needed is None and others:
            raise ValueError(f"rule {self.rule!r} takes no number; remove {others}")
        return self

    @property
    def number(self) -> int | float:
        """The number the rule takes (``n_synapses``, ``indegree``, ...); NaN
        for a rule that takes none."""
        return getattr(self, RULE_NUMBER[self.rule]) if self.rule in RULE_NUMBER else math.nan


class ConnectivityFile(FrozenConfig):
    """``connectivity.yaml``.

    Each row is a :class:`ConnectionConfig`: ``source``/``target`` names, a
    ``rule`` with its number, an optional ``synapse`` and a ``weight`` /
    ``delay`` distribution (above). A pair may have several rows with
    different synapses (e.g. AMPA and NMDA).

    The rows are listed under ``connections``, or, for a large network, kept
    in a CSV file named by ``connections_file`` (one row per connection, the
    same fields; see ``config/connection_table.py``). Give one of the two.
    """

    connections: list[ConnectionConfig] | None = Field(
        default=None,
        description="one entry per (source, target, synapse); leave a pair out rather "
        "than writing n_synapses: 0. Required unless connections_file is given",
    )
    connections_file: str | None = Field(
        default=None,
        description="instead of connections: a CSV file, relative to the network folder, "
        "with one row per connection (e.g. connections.csv), for a large network",
    )
    @model_validator(mode="before")
    @classmethod
    def _refuse_network_bound_mode(cls, data):
        if isinstance(data, dict) and "bound_mode" in data:
            raise ValueError(
                "bound_mode at the top of connectivity.yaml was removed: each weight and delay has its "
                "own, with its bound (e.g. weight: {distribution: normal, mean: 87.8, std: 8.78, "
                "lower_bound: 0, bound_mode: redraw, unit: pA})"
            )
        return data

    @model_validator(mode="after")
    def _check_one_source_of_rows(self) -> ConnectivityFile:
        if (self.connections is None) == (self.connections_file is None):
            raise ValueError("give either connections (a list) or connections_file (a CSV file)")
        return self
