"""What ``connectivity.yaml`` may contain: one row per projection.

``WeightDistribution`` and ``DelayDistribution`` are also used by background
inputs and stimuli.
"""

from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import (
    BeforeValidator,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    model_validator,
)

from microcircuit_lab.config.frozen_config import FrozenConfig

#: The distributions every backend draws weights and delays from. Any other
#: name is a project distribution, with ``parameters``, which the backend
#: defines (see its ``models.py``).
SHARED_DISTRIBUTIONS = ("normal", "uniform", "lognormal", "fixed")

Parameters = dict[str, StrictInt | StrictFloat | StrictBool] | None


#: The weight units of earlier versions, and what to write instead.
OLD_UNITS = {
    "PSP": "unit: PSP was removed, so that the files show the weight the simulator gets: convert the "
    "PSP in the builder (e.g. builder_tools.psp_to_psc_iaf_psc_exp) and write unit: pA",
    "PSC": "unit: PSC is now written unit: pA",
    "native": "unit: native was removed: write the weight's unit, pA, nS or mV",
}


def _refuse_old_unit(unit):
    if isinstance(unit, str) and unit in OLD_UNITS:
        raise ValueError(OLD_UNITS[unit])
    return unit


def _check_parameters(distribution: str, parameters: Parameters) -> None:
    if parameters is not None and distribution in SHARED_DISTRIBUTIONS:
        raise ValueError(
            f"distribution {distribution!r} takes no parameters (only a project distribution does)"
        )


class WeightDistribution(FrozenConfig):
    """
    Distribution of synaptic weights.

    ``mean`` is the weight the simulator gets, and ``unit`` says its unit:
    ``pA`` (a current), ``nS`` (a conductance) or ``mV`` (a jump of the
    membrane potential). The core converts nothing with it; it is required,
    so the files say what each number is. Only current weights (``pA``) are
    in the scaling's compensation, whose mean current needs them.
    """

    mean: float = Field(
        examples=[0.15],
        description="amplitude, in the unit set by `unit`; a negative weight is inhibitory",
    )
    rel_std: float = Field(ge=0.0, examples=[0.1], description="standard deviation / |mean|")

    # To add a shared distribution: list it in SHARED_DISTRIBUTIONS and draw it
    # in create_weight_spec / create_delay_parameter (backends/nest/distributions.py)
    # and in backends/brian2/distributions.py.
    distribution: str = Field(
        default="normal",
        description="how each weight is drawn, with that mean and standard deviation: normal, "
        "uniform, lognormal or fixed; or the name of a project distribution, which the backend "
        "defines, with parameters",
    )
    parameters: Parameters = Field(
        default=None,
        description="only for a project distribution: the values its expression uses, e.g. "
        "{length: 20}",
    )

    unit: Annotated[Literal["pA", "nS", "mV"], BeforeValidator(_refuse_old_unit)] = Field(
        examples=["pA"],
        description="the unit of the weight: pA (a current), nS (a conductance) or mV (a jump of the "
        "membrane potential); nothing is converted",
    )

    @model_validator(mode="after")
    def _check_parameters(self) -> WeightDistribution:
        _check_parameters(self.distribution, self.parameters)
        return self


class DelayDistribution(FrozenConfig):
    """Distribution describing synaptic delays."""

    mean: float = Field(gt=0.0, examples=[1.5], description="mean delay (ms)")
    rel_std: float = Field(ge=0.0, examples=[0.5], description="standard deviation / mean")
    distribution: str = Field(
        default="normal",
        description="how each delay is drawn, with that mean and standard deviation: normal, "
        "uniform, lognormal or fixed; or the name of a project distribution, with parameters",
    )
    parameters: Parameters = Field(
        default=None,
        description="only for a project distribution: the values its expression uses",
    )
    minimum: float | None = Field(
        default=None,
        gt=0.0,
        examples=[0.1],
        description="smallest allowed delay (ms) of a drawn delay, never below half the "
        "simulation step; omit for half the simulation step",
    )

    @model_validator(mode="after")
    def _check_parameters(self) -> DelayDistribution:
        _check_parameters(self.distribution, self.parameters)
        return self


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
    name is looked up by the backend (see ``SHARED_RULES``) and takes
    ``parameters`` instead of a number.

    The core computes with the expected number of synapses
    (``builder_tools.mean_input.expected_synapses``), and ``scale_network`` scales
    the given number (``builder_tools.scaling.scale_rule_number``). Any other rule
    cannot be scaled yet.
    """

    source: str = Field(examples=["L4_E"], description="source population name")
    target: str = Field(examples=["L23_E"], description="target population name")
    rule: str = Field(
        default="fixed_total_number",
        description="how the synapses are placed: fixed_total_number, fixed_indegree, "
        "fixed_outdegree or pairwise_bernoulli, each with its own number (n_synapses, indegree, "
        "outdegree or p); one_to_one or all_to_all, with no number; or another rule, which the "
        "simulator looks up, with parameters",
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
    parameters: Parameters = Field(
        default=None,
        description="only for a rule that is not shared: its parameters, e.g. "
        "{width: 10, p0: 0.5}",
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
        if self.parameters is not None and self.rule in SHARED_RULES:
            raise ValueError(f"rule {self.rule!r} takes no parameters (only a rule that is not shared does)")
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
    bound_mode: Literal["redraw", "clip"] = Field(
        default="redraw",
        description="what to do with a drawn weight or delay outside its allowed "
        "range: 'redraw' draws again, 'clip' replaces it by the limit; applies to "
        "all weights and delays of the network, background inputs included",
    )

    @model_validator(mode="after")
    def _check_one_source_of_rows(self) -> ConnectivityFile:
        if (self.connections is None) == (self.connections_file is None):
            raise ValueError("give either connections (a list) or connections_file (a CSV file)")
        return self
