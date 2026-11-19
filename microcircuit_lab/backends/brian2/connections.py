"""
Who connects to whom in the Brian2 backend, for each connection rule.

All rows of the connection table between two Brian2 groups through the same
synapse go into one ``Synapses`` object (see ``simulator.py``), made by the
``Synapses.connect`` calls made here:

- The rows with multapses (NEST's default) under fixed_total_number,
  fixed_indegree or fixed_outdegree: their pairs are drawn here with numpy
  and given to Brian2 as arrays, in one call for all of them. Nothing is
  compiled, so this takes about the same time for any number of rows.
- Any other row: one call each, in which Brian2 draws the pairs itself (in
  C++ standalone mode, in C++) and reads the row's numbers from the
  namespace, so the calls of one rule share their compiled code.

The pairs are drawn as NEST draws them: autapses and multapses are allowed
unless the connection says otherwise, and without multapses no pair is drawn
twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import brian2 as b2
import numpy as np
from brian2.utils.stringtools import word_substitute

from microcircuit_lab.backends.brian2.models import ConnectionRule
from microcircuit_lab.config.connectivity import RULE_NUMBER, SHARED_RULES


@dataclass(frozen=True)
class Row:
    """One row of the connection table: its rule and number (or, for a
    project rule, its definition and arguments), and where its source and
    target populations are in their Brian2 groups."""

    rule: str
    number: float
    source_start: int
    source_size: int
    target_start: int
    target_size: int
    autapses: bool
    multapses: bool
    same_population: bool
    arguments: dict = field(default_factory=dict)
    definition: ConnectionRule | None = None

    @property
    def no_autapses(self) -> int:
        """1 if a neuron may not connect to itself, else 0."""
        return int(self.same_population and not self.autapses)


def table(values, name: str) -> b2.TimedArray:
    """A lookup table for Brian2 expressions: read at time k seconds, it gives
    ``values[k]`` (a 2D one, read at (k seconds, n), gives ``values[k, n]``).

    ``name`` must be unique in the network. Brian2 puts it in the code it
    generates, so the same name from run to run lets it reuse its compiled
    code (see simulator.py)."""

    return b2.TimedArray(np.asarray(values, dtype=float), dt=1 * b2.second, name=name)


def _counts(row: Row, rng: np.random.Generator) -> np.ndarray:
    """How many synapses each neuron of the row's outer population makes: its
    sources for fixed_total_number and fixed_outdegree, its targets for
    fixed_indegree."""

    if row.rule == "fixed_total_number":
        return rng.multinomial(int(row.number), np.full(row.source_size, 1.0 / row.source_size))
    size = row.source_size if row.rule == "fixed_outdegree" else row.target_size
    return np.full(size, int(row.number))


def _pairs(row: Row, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """
    The synapses of a row with multapses, as (sources, targets) in their
    Brian2 groups: each neuron of the outer population makes its number of
    synapses (see _counts), and the other end of each is drawn uniformly
    from the other population (without the neuron itself, without autapses).
    """

    inward = row.rule == "fixed_indegree"
    outer_start = row.target_start if inward else row.source_start
    other_start, other_size = (row.source_start, row.source_size) if inward else (row.target_start, row.target_size)

    counts = _counts(row, rng)
    # 32-bit indices, as Brian2 keeps them: half the memory of numpy's default.
    outer = np.repeat(np.arange(counts.size, dtype=np.int32), counts)
    other = rng.integers(0, other_size - row.no_autapses, size=outer.size, dtype=np.int32)
    # Without autapses, the neuron itself is skipped: the ones after it move up by one.
    other += row.no_autapses * (other >= outer)

    outer += outer_start
    other += other_start
    return (other, outer) if inward else (outer, other)


def _single(row: Row, n_source: int, prefix: str, rng) -> tuple[dict, dict, int]:
    """One ``connect`` call for one row: pairwise_bernoulli, one_to_one,
    all_to_all, a project rule, or a rule without multapses.

    The row's numbers go in the namespace, not in the code: the calls of the
    same rule then have the same code, which Brian2 compiles once."""

    ns, nt, self_ = row.source_size, row.target_size, row.no_autapses
    namespace = {
        "source_start": row.source_start,
        "source_size": ns,
        "target_start": row.target_start,
        "target_size": nt,
        "no_autapses": self_,
    }
    in_source = "i >= source_start and i < source_start + source_size"
    in_target = "j >= target_start and j < target_start + target_size"
    not_self = " and k != i" if self_ else ""

    if row.rule == "one_to_one":
        # The populations have the same size: the k-th source to the k-th target.
        k = "i - source_start + target_start"
        return {"j": f"k for k in range({k}, {k} + 1) if {in_source}{not_self}"}, namespace, ns * (1 - self_)

    if row.rule == "all_to_all":
        j = f"k for k in range(target_start, target_start + target_size) if {in_source}{not_self}"
        return {"j": j}, namespace, ns * (nt - self_)

    if row.definition is not None:
        rule = row.definition
        # The arguments get a prefix, so that none takes the place of the
        # row's numbers above.
        names = {name: f"rule_{name}" for name in row.arguments}
        condition = f"{in_source}{not_self} and ({word_substitute(rule.condition, names)})"
        if rule.p != "1":
            condition += f" and rand() < ({word_substitute(rule.p, names)})"
        arguments = {"j": f"k for k in range(target_start, target_start + target_size) if {condition}"}
        if rule.n != "1":
            arguments["n"] = word_substitute(rule.n, names)
        namespace.update({names[name]: value for name, value in row.arguments.items()})
        # The count is known only once Brian2 has drawn the pairs: at most every pair.
        return arguments, namespace, ns * (nt - self_)

    if row.rule == "pairwise_bernoulli":
        namespace["probability"] = min(float(row.number), 1.0)
        j = f"k for k in sample(target_start, target_start + target_size, p=probability) if {in_source}{not_self}"
        return {"j": j}, namespace, round(namespace["probability"] * ns * (nt - self_))

    namespace["number"] = int(row.number)

    if row.rule == "fixed_indegree":
        drawn = "source_start + (k + no_autapses*(j - source_start + 1)) % source_size"
        i = f"{drawn} for k in sample(source_size - no_autapses, size=number) if {in_target}"
        return {"i": i}, namespace, int(row.number) * nt

    drawn = "target_start + (k + no_autapses*(i - target_start + 1)) % target_size"
    if row.rule == "fixed_outdegree":
        j = f"{drawn} for k in sample(target_size - no_autapses, size=number) if {in_source}"
        return {"j": j}, namespace, int(row.number) * ns

    # fixed_total_number without multapses: how many synapses each source makes,
    # then that many distinct targets.
    counts = np.zeros(n_source)
    counts[row.source_start:row.source_start + ns] = rng.multivariate_hypergeometric(
        np.full(ns, nt - self_), int(row.number)
    )
    size = f"int({prefix}count(i*second))"
    namespace[f"{prefix}count"] = table(counts, f"{prefix}count")
    return {"j": f"{drawn} for k in sample(target_size - no_autapses, size={size})"}, namespace, int(row.number)


def connect_calls(
    rows: list[Row], n_source: int, rng: np.random.Generator, name: str
) -> tuple[list[tuple[dict, dict]], list[int]]:
    """
    The ``Synapses.connect`` calls that make the rows of one ``Synapses``
    object named ``name``, as ``(arguments, namespace)``, and the number of
    synapses of each row (expected, for pairwise_bernoulli), in the order of
    ``rows``.

    Raises
    ------
    ValueError
        If a row asks for more distinct pairs than there are, without multapses.
    """

    for row in rows:
        if row.rule not in RULE_NUMBER:
            if row.rule not in SHARED_RULES and row.definition is None:
                raise ValueError(f"Unknown connection rule: {row.rule!r}")
            continue
        if row.multapses or row.rule == "pairwise_bernoulli":
            continue
        available = (row.source_size if row.rule == "fixed_indegree" else row.target_size) - row.no_autapses
        wanted = int(row.number)
        if row.rule == "fixed_total_number":
            available *= row.source_size
        if wanted > available:
            raise ValueError(
                f"{row.rule} {wanted} is more than the {available} pairs there are, without multapses."
            )

    calls: list[tuple[dict, dict]] = []
    numbers: dict[int, int] = {}
    # The rows with multapses: their pairs drawn here (see _pairs), one call for all.
    drawn = [k for k, row in enumerate(rows)
             if row.multapses and row.rule in ("fixed_total_number", "fixed_indegree", "fixed_outdegree")]
    if drawn:
        pairs = [_pairs(rows[k], rng) for k in drawn]
        calls.append(({"i": np.concatenate([i for i, _ in pairs]), "j": np.concatenate([j for _, j in pairs])}, {}))
        numbers.update((k, i.size) for k, (i, _) in zip(drawn, pairs))

    # Any other row: one call each, Brian2 draws its pairs.
    for k, row in enumerate(rows):
        if k not in numbers:
            arguments, namespace, numbers[k] = _single(row, n_source, f"{name}_c{k}_", rng)
            calls.append((arguments, namespace))

    return calls, [numbers[k] for k in range(len(rows))]
