"""What ``connectivity.yaml`` may contain: one row per projection. Its
weight and delay are in ``config/distributions.py``."""

from __future__ import annotations

import math

from pydantic import ConfigDict, Field, model_validator

from microcircuit_lab.config.distributions import (
    Arguments,
    DelayDistribution,
    WeightDistribution,
    old_field_message,
)
from microcircuit_lab.config.frozen_config import FrozenConfig

# The field holding the number each connection rule takes.
RULE_NUMBER = {
    "fixed_total_number": "n_synapses",
    "fixed_indegree": "indegree",
    "fixed_outdegree": "outdegree",
    "pairwise_bernoulli": "p",
}

#: The rules every backend implements. Any other name is looked up by the
#: backend: a rule of the simulator or of the project.
SHARED_RULES = (*RULE_NUMBER, "one_to_one", "all_to_all", "from_file")


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
    neuron; the populations have the same size) and ``all_to_all``.
    ``from_file`` takes every synapse from the CSV ``file`` (see
    ``config/synapse_files.py``): the entry gives only the weight's unit
    (``weight: {unit: pA}``) and no delay. Any other
    name is looked up by the backend (see ``SHARED_RULES``) and takes its
    arguments as keys of their own instead of a number
    (``{rule: pairwise_poisson, pairwise_avg_num_conns: 0.3}``). Any rule passes such
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
        "outdegree or p); one_to_one or all_to_all, with no number; from_file, with its file; or another "
        "rule, which the simulator looks up, with its arguments as keys of their own (e.g. "
        "pairwise_avg_num_conns: 0.3)",
    )
    file: str | None = Field(
        default=None,
        description="from_file: CSV file, relative to the network folder (e.g. synapses/E_to_I.csv), with one row per synapse: "
        "source_index and target_index (from 0 in each population), weight (in the weight's unit) and "
        "delay (ms)",
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
    weight: WeightDistribution = Field(
        description="weight of each synapse; with rule: from_file, only its unit (the file gives the weights)"
    )
    delay: DelayDistribution = Field(
        default_factory=DelayDistribution,
        description="delay of each synapse; required, except with rule: from_file (the file gives the delays)",
    )

    @model_validator(mode="before")
    @classmethod
    def _refuse_parameters_and_number(cls, data):
        if isinstance(data, dict) and "parameters" in data:
            raise ValueError(old_field_message("parameters"))
        # "number" is the table's column for the rule's number, not an argument.
        if isinstance(data, dict) and "number" in data:
            raise ValueError(f"number is not a key of a connection: write the rule's number under its name, "
                             f"one of {list(RULE_NUMBER.values())}")
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

    @model_validator(mode="after")
    def _check_file_matches_rule(self) -> ConnectionConfig:
        from_file = self.rule == "from_file"
        if from_file != (self.file is not None):
            raise ValueError("rule from_file needs file (the CSV file of its synapses); no other rule takes file")
        if from_file and (self.model_extra or self.allow_autapses is not None or self.allow_multapses is not None):
            raise ValueError("rule from_file: the file gives every synapse; remove allow_autapses, "
                             "allow_multapses and any argument")
        problems = [f"{what}.{problem}" for what in ("weight", "delay")
                    for problem in getattr(self, what).problems(from_file=from_file)]
        if problems:
            raise ValueError("; ".join(problems))
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
