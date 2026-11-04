"""Values drawn from a distribution: the weight and delay of each synapse
(connections, background inputs, stimuli), and values drawn for every neuron
(neuron parameters in ``neurons.yaml``, initial states in ``populations.yaml``).

Each is a fixed value (for a neuron, a plain number) or a ``distribution``
with the fields it takes, and optional bounds, written the same way
everywhere: ``{distribution: normal, mean: -58, std: 10}``.
"""

from __future__ import annotations

import typing
from typing import Annotated, Any, ClassVar, Literal

import numpy as np
from pydantic import (
    BeforeValidator,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    model_serializer,
    model_validator,
)

from microcircuit_lab.config.frozen_config import FrozenConfig

#: The distributions every backend draws weights and delays from, and the
#: fields each one takes: the mean and standard deviation of the drawn values,
#: or the range of a uniform draw. Any other name is looked up by the backend:
#: the simulator's own (NEST's ``exponential``) or the project's (see
#: ``extensions/``), with its arguments as keys of their own. A weight has the
#: same fields as a delay (DelayDistribution), and its unit.
SHARED_DISTRIBUTIONS = {"normal": ("mean", "std"), "lognormal": ("mean", "std"), "uniform": ("min", "max")}

#: What to do with a drawn weight or delay outside its bounds.
BoundMode = Literal["redraw", "clip"]

#: The arguments of a rule or distribution that is not shared, each a key of
#: its own next to the fields (``{rule: pairwise_poisson, pairwise_avg_num_conns: 0.3}``,
#: ``{distribution: exponential, beta: 2}``).
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
            "distribution (e.g. {rule: pairwise_poisson, pairwise_avg_num_conns: 0.3} or {distribution: erlang2, "
            "beta: 20, mean: 40, unit: pA}); in a CSV file, one column per argument (pairwise_avg_num_conns, weight.beta)"
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


def is_unset(values):
    """Whether a value is not set: None (text) or NaN (numbers). For an
    array, one boolean per value."""
    if not isinstance(values, np.ndarray):
        return values is None or values != values
    if values.dtype.kind == "f":
        return np.isnan(values)
    return np.array([value is None or value != value for value in values], dtype=bool)


def drawn_value_problems(fields: dict[str, np.ndarray], kind: str) -> list[tuple[str, np.ndarray, str]]:
    """
    Where the fields of weights, delays or neuron values (``kind``:
    ``"weight"``, ``"delay"`` or ``"neuron"``) do not fit together, as
    ``(field, rows, message)``, ``rows`` a boolean array.

    ``fields`` holds each field (``distribution``, ``value``, ``mean``, ...,
    ``bound_mode``) and each argument of a distribution that is not shared as
    an array with one entry per value, so the same checks serve one entry of
    a file and the millions of rows of a connection table. A field's own
    limits (e.g. ``std`` >= 0) are checked by pydantic with its ``Field``.
    """

    distribution = fields["distribution"]
    arguments = [name for name in fields if name not in DelayDistribution.model_fields]
    given = {name: ~is_unset(values) for name, values in fields.items()}
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
        if kind == "weight":
            other = ~fixed & ~np.logical_or.reduce(list(kinds.values()))
            checks.append(("mean", other & ~given["mean"],
                           "a weight from a distribution that is not shared needs mean, the mean of its "
                           "values: its sign tells an excitatory weight from an inhibitory one"))
        if kind == "delay":
            checks += [
                ("lower_bound", ~fixed & ~given["lower_bound"],
                 "a drawn delay needs lower_bound (ms), e.g. the simulation step, with bound_mode"),
                ("value", fixed & (fields["value"] <= 0), "a delay must be greater than 0"),
                ("mean", (kinds["normal"] | kinds["lognormal"]) & (fields["mean"] <= 0),
                 "a delay's mean must be greater than 0"),
            ]
    return [(field, rows, message) for field, rows, message in checks if rows.any()]


class DrawnValue(FrozenConfig):
    """
    What weights, delays and neuron values share: a fixed ``value``, or a
    ``distribution`` to draw each one from, with the fields it takes; and
    optional bounds. The fields are declared by each (their units and
    examples differ); the checks are here.

    ``mean`` and ``std`` are those of the drawn values, for every
    distribution: a lognormal value with mean -351.2 and std 35.1 has that
    mean and standard deviation (and the sign of its mean); the backend
    finds the log-space numbers it draws with.
    """

    # To add a shared distribution: list it in SHARED_DISTRIBUTIONS and draw it
    # in backends/nest/distributions.py and backends/brian2/distributions.py.

    # Any other key is an argument of a distribution that is not shared.
    model_config = ConfigDict(frozen=True, extra="allow")
    __pydantic_extra__: Arguments = Field(init=False)

    #: Which checks of drawn_value_problems apply: "weight", "delay" or "neuron".
    kind: ClassVar[str]

    @model_validator(mode="before")
    @classmethod
    def _refuse_old_fields(cls, data):
        old = [old_field_message(name) for name in data if old_field_message(name)] if isinstance(data, dict) else []
        if old:
            raise ValueError("; ".join(old))
        return data

    @model_serializer(mode="wrap")
    def _leave_out_unset(self, handler):
        # Written out, only what is set: {distribution: normal, mean: ..., std: ...}.
        return {name: value for name, value in handler(self).items() if value is not None}

    @property
    def fields(self) -> dict[str, Any]:
        """Every field (None where not set; a neuron value has no ``value``)
        and every argument, by name, as the backends draw from them."""
        return {name: getattr(self, name, None) for name in DelayDistribution.model_fields} | self.model_extra

    @model_validator(mode="after")
    def _check_fields_fit(self):
        # The fields as columns of one row, as a connection table holds them.
        columns = {
            name: np.array([value], dtype=float if name not in DelayDistribution.model_fields or is_number_field(name)
                           else object)
            for name, value in self.fields.items()
        }
        for field, _, message in drawn_value_problems(columns, self.kind):
            raise ValueError(f"{field}: {message}")
        return self

    @property
    def expected(self) -> float:
        """The mean of the values, before any bound: ``value``, ``mean``, or
        the middle of ``min`` and ``max``. NaN for a distribution that is not
        shared and has no ``mean``."""
        return expected_value(self.fields)


def lognormal_parameters(mean: float, std: float) -> tuple[float, float]:
    """
    The ``mu`` and ``sigma`` of the normal distribution whose exponential
    has the mean ``|mean|`` and the standard deviation ``std``, which
    simulators draw a lognormal value with; the value then takes the sign of
    ``mean``.
    """
    sigma_squared = np.log1p(std**2 / mean**2)
    return np.log(abs(mean)) - 0.5 * sigma_squared, np.sqrt(sigma_squared)


def not_shared_rows(distribution: np.ndarray) -> np.ndarray:
    """Where a column of distribution names holds one that is not shared
    (the simulator's own or the project's; ``None`` is a fixed value)."""
    shared = np.logical_or.reduce([distribution == name for name in SHARED_DISTRIBUTIONS])
    return ~is_unset(distribution) & ~shared


def expected_values(fields: dict[str, np.ndarray]) -> np.ndarray:
    """
    The mean of each weight or delay before any bound, from the arrays of
    its fields (see :func:`drawn_value_problems`): ``value`` for a fixed one,
    the middle of ``min`` and ``max`` for a uniform one, else ``mean`` (NaN
    for a distribution that is not shared and has none).
    """

    distribution = fields["distribution"]
    fixed = ~~is_unset(distribution)
    middle = (fields["min"] + fields["max"]) / 2
    return np.where(fixed, fields["value"], np.where(distribution == "uniform", middle, fields["mean"]))


def expected_value(fields: dict[str, Any]) -> float:
    """:func:`expected_values` of one weight or delay, from its fields (a
    number left out is None or NaN)."""
    return float(expected_values({
        name: np.array([fields[name]], dtype=float if is_number_field(name) else object)
        for name in ("distribution", "value", "mean", "min", "max")
    })[0])


class WeightDistribution(DrawnValue):
    """
    The weight of each synapse: a fixed ``value``, or drawn from a
    ``distribution``, in ``unit``: ``pA`` (a current), ``nS`` (a conductance)
    or ``mV`` (a jump of the membrane potential). The core converts nothing
    with it; it is required, so the files say what each number is. Only
    current weights (``pA``) are in the scaling's compensation, whose mean
    current needs them. A negative weight is inhibitory.
    """

    kind: ClassVar[str] = "weight"

    distribution: str | None = Field(
        default=None,
        examples=["normal"],
        description="how each weight is drawn: normal or lognormal, with mean and std; uniform, "
        "with min and max; or another name, which the simulator looks up (its own, e.g. NEST's "
        "exponential, or the project's), with its arguments as keys of their own (e.g. beta: 20) and "
        "the mean of its values. Omit it for a fixed weight",
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


class DelayDistribution(DrawnValue):
    """The delay (ms) of each synapse: a fixed ``value``, or drawn from a
    ``distribution``, with a ``lower_bound``."""

    kind: ClassVar[str] = "delay"

    distribution: str | None = Field(
        default=None,
        examples=["normal"],
        description="how each delay is drawn: normal or lognormal, with mean and std; uniform, with "
        "min and max; or another name, which the simulator looks up (its own, e.g. NEST's exponential, "
        "or the project's), with its arguments as keys of their own. Omit it for a fixed delay",
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


class DrawnNeuronValue(DrawnValue):
    """
    A value drawn for every neuron from a ``distribution``: normal or
    lognormal, with ``mean`` and ``std``; uniform, with ``min`` and ``max``;
    or another name, which the simulator looks up (its own, e.g. NEST's
    ``exponential``, or the project's), with its arguments as keys of their
    own (``{distribution: exponential, beta: 2}``). Optional bounds, as for
    a weight.
    """

    kind: ClassVar[str] = "neuron"

    distribution: str = Field(
        examples=["normal"],
        description="how each neuron's value is drawn: normal or lognormal, with mean and std; uniform, "
        "with min and max; or another name, which the simulator looks up (its own, e.g. NEST's "
        "exponential, or the project's), with its arguments as keys of their own (e.g. beta: 2)",
    )
    mean: float | None = Field(default=None, examples=[-58.0], description="mean of the drawn values (normal, lognormal)")
    std: float | None = Field(
        default=None, ge=0.0, examples=[10.0], description="standard deviation of the drawn values (normal, lognormal)"
    )
    min: float | None = Field(default=None, description="smallest value a uniform draw gives")
    max: float | None = Field(default=None, description="largest value a uniform draw gives")
    lower_bound: float | None = Field(default=None, description="smallest allowed drawn value; omit for none")
    upper_bound: float | None = Field(default=None, description="largest allowed drawn value; omit for none")
    bound_mode: BoundMode | None = Field(
        default=None,
        description="with a bound: what to do with a drawn value past it: redraw draws it again, clip sets it "
        "to the bound",
    )


PerNeuronValue = StrictInt | StrictFloat | DrawnNeuronValue
