"""
Who connects to whom in the Brian2 backend, for each connection rule.

All rows of the connection table between two Brian2 groups through the same
synapse go into one ``Synapses`` object (see ``simulator.py``), and Brian2 draws
their pairs itself, from the ``Synapses.connect`` calls made here, so the
indices of millions of synapses are never held in Python (in C++ standalone
mode they are drawn in C++). Each call is one more piece of generated code, so
the rows with multapses (NEST's default) are made by one call for all of them;
the others by one call each.

The pairs are drawn as NEST draws them: autapses and multapses are allowed
unless the connection says otherwise, and without multapses no pair is drawn
twice.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import brian2 as b2
import numpy as np

from microcircuit_lab.backends.brian2.models import ConnectionRule
from microcircuit_lab.config.connectivity import RULE_NUMBER, SHARED_RULES


@dataclass(frozen=True)
class Row:
    """One row of the connection table: its rule and number (or, for a
    project rule, its definition and parameters), and where its source and
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
    parameters: dict = field(default_factory=dict)
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


def _merged(rows: list[Row], outward: bool, n_outer: int, prefix: str, rng) -> tuple[dict, dict, list[int]]:
    """
    One ``connect`` call for rows with multapses: for each neuron of an outer
    population (the sources, or the targets of fixed_indegree), its k-th
    synapse belongs to the row whose cumulative count it is under, and its
    other end is drawn uniformly from that row's other population (without
    the neuron itself, without autapses). One call for all rows is faster
    than one per row or per population, in both devices: each call costs
    Brian2 a fixed time, more than the table reads it saves.
    """

    outer, drawn = ("i", "j") if outward else ("j", "i")
    by_outer = defaultdict(list)
    for row in rows:
        by_outer[row.source_start if outward else row.target_start].append(row)
    slots = max(len(members) for members in by_outer.values())

    cum = np.zeros((slots, n_outer))
    population = np.zeros(n_outer)
    first, size, no_autapses = (np.zeros(len(by_outer) * slots) for _ in range(3))
    size += 1
    numbers = []
    for p, (start, members) in enumerate(by_outer.items()):
        n = members[0].source_size if outward else members[0].target_size
        population[start:start + n] = p
        running = np.zeros(n)
        for q in range(slots):
            if q < len(members):
                row = members[q]
                counts = _counts(row, rng)
                running += counts
                numbers.append(int(counts.sum()))
                slot = p * slots + q
                first[slot] = row.target_start if outward else row.source_start
                size[slot] = row.target_size if outward else row.source_size
                no_autapses[slot] = row.no_autapses
            cum[q, start:start + n] = running

    # The row (slot) of the k-th synapse: how many cumulative counts it is past.
    slot = " + ".join([f"int(k >= {prefix}cum({q}*second, {outer}))" for q in range(slots - 1)] or ["0"])
    slot = f"int({prefix}population({outer}*second))*{slots} + {slot}"

    def read(name: str) -> str:
        return f"int({prefix}{name}(({slot})*second))"

    expression = (
        f"{read('first')} + (int(rand()*({read('size')} - {read('self')})) "
        f"+ {read('self')}*({outer} - {read('first')} + 1)) % {read('size')}"
    )
    total = f"int({prefix}cum({slots - 1}*second, {outer}))"
    if outward:
        arguments = {drawn: f"{expression} for k in range({total})"}
    else:
        # Brian2 wants a constant range for i: up to the largest count, then
        # only the target's own.
        arguments = {drawn: f"{expression} for k in range({int(cum[-1].max())}) if k < {total}"}
    namespace = {
        f"{prefix}{name}": table(values, f"{prefix}{name}")
        for name, values in (
            ("cum", cum), ("population", population), ("first", first), ("size", size), ("self", no_autapses)
        )
    }
    return arguments, namespace, numbers


def _single(row: Row, n_source: int, prefix: str, rng) -> tuple[dict, dict, int]:
    """One ``connect`` call for one row: pairwise_bernoulli, one_to_one,
    all_to_all, a project rule, or a rule without multapses."""

    s0, ns, t0, nt, self_ = row.source_start, row.source_size, row.target_start, row.target_size, row.no_autapses
    in_source = f"i >= {s0} and i < {s0 + ns}"
    in_target = f"j >= {t0} and j < {t0 + nt}"
    not_self = " and k != i" if self_ else ""

    if row.rule == "one_to_one":
        # The populations have the same size: the k-th source to the k-th target.
        k = f"i - {s0} + {t0}"
        return {"j": f"k for k in range({k}, {k} + 1) if {in_source}{not_self}"}, {}, ns * (1 - self_)

    if row.rule == "all_to_all":
        return {"j": f"k for k in range({t0}, {t0 + nt}) if {in_source}{not_self}"}, {}, ns * (nt - self_)

    if row.definition is not None:
        rule = row.definition
        condition = f"{in_source}{not_self} and ({rule.condition})"
        if rule.p != "1":
            condition += f" and rand() < ({rule.p})"
        arguments = {"j": f"k for k in range({t0}, {t0 + nt}) if {condition}"}
        if rule.n != "1":
            arguments["n"] = rule.n
        # The count is known only once Brian2 has drawn the pairs: at most every pair.
        return arguments, dict(row.parameters), ns * (nt - self_)

    if row.rule == "pairwise_bernoulli":
        p = min(float(row.number), 1.0)
        condition = in_source + (" and k != i" if self_ else "")
        return {"j": f"k for k in sample({t0}, {t0 + nt}, p={p}) if {condition}"}, {}, round(p * ns * (nt - self_))

    if row.rule == "fixed_indegree":
        k = int(row.number)
        drawn = f"{s0} + (k + {self_}*(j - {s0} + 1)) % {ns}"
        return {"i": f"{drawn} for k in sample({ns - self_}, size={k}) if {in_target}"}, {}, k * nt

    if row.rule == "fixed_outdegree":
        k = int(row.number)
        drawn = f"{t0} + (k + {self_}*(i - {t0} + 1)) % {nt}"
        return {"j": f"{drawn} for k in sample({nt - self_}, size={k}) if {in_source}"}, {}, k * ns

    # fixed_total_number without multapses: how many synapses each source makes,
    # then that many distinct targets.
    counts = np.zeros(n_source)
    counts[s0:s0 + ns] = rng.multivariate_hypergeometric(np.full(ns, nt - self_), int(row.number))
    drawn = f"{t0} + (k + {self_}*(i - {t0} + 1)) % {nt}"
    size = f"int({prefix}count(i*second))"
    return (
        {"j": f"{drawn} for k in sample({nt - self_}, size={size})"},
        {f"{prefix}count": table(counts, f"{prefix}count")},
        int(row.number),
    )


def connect_calls(
    rows: list[Row], n_source: int, n_target: int, rng: np.random.Generator, name: str
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
    outward = [k for k, row in enumerate(rows) if row.multapses and row.rule in ("fixed_total_number", "fixed_outdegree")]
    inward = [k for k, row in enumerate(rows) if row.multapses and row.rule == "fixed_indegree"]

    for members, is_outward, n_outer in ((outward, True, n_source), (inward, False, n_target)):
        if not members:
            continue
        arguments, namespace, counts = _merged([rows[k] for k in members], is_outward, n_outer, f"{name}_c{len(calls)}_", rng)
        calls.append((arguments, namespace))
        # _merged counts rows grouped by their outer population.
        by_outer = defaultdict(list)
        for k in members:
            by_outer[rows[k].source_start if is_outward else rows[k].target_start].append(k)
        order = [k for group in by_outer.values() for k in group]
        numbers.update(zip(order, counts))

    for k, row in enumerate(rows):
        if k in numbers:
            continue
        arguments, namespace, number = _single(row, n_source, f"{name}_c{len(calls)}_", rng)
        calls.append((arguments, namespace))
        numbers[k] = number

    return calls, [numbers[k] for k in range(len(rows))]
