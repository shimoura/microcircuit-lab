"""
Checks of the Brian2 backend, run by ``Brian2Backend.check``.

Functions of ``Brian2Backend`` (``simulator.py``), kept here to keep that file
short; each takes the backend and raises if the network, the models or the
recording ask for something Brian2 cannot do.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import numpy as np

from microcircuit_lab.backends.brian2 import models
from microcircuit_lab.config.connectivity import SHARED_RULES
from microcircuit_lab.config.distributions import is_unset
from microcircuit_lab.config.stimuli import DcStimulusConfig

if TYPE_CHECKING:
    from microcircuit_lab.backends.brian2.simulator import Brian2Backend


def _names(*expressions: str) -> set[str]:
    """The names the Brian2 expressions use."""
    return set(re.findall(r"[A-Za-z_]\w*", " ".join(expressions)))


def check_models_exist(backend: Brian2Backend) -> None:
    """Raise if a population or a synapse names a model that is not defined."""

    for population in backend.network.populations:
        backend.neuron_model(population)
    for synapse in backend.network.synapses:
        backend.synapse_model(synapse)


def check_rules_exist(backend: Brian2Backend) -> None:
    """Raise if a connection names a project rule that is not defined."""

    table = backend.network.connections
    for name in sorted(set(table["rule"][~np.isin(table["rule"], SHARED_RULES)].tolist())):
        if name not in backend._connection_rules:
            raise models.missing_model_error("rule", name, backend._connection_rules)


def check_distributions(backend: Brian2Backend) -> None:
    """Raise if a distribution is not defined, needs ``redraw_rounds``, or is given an
    argument its expression does not use."""

    for use in backend.network.distributions_not_shared():
        if use.name not in backend._distributions:
            raise models.missing_model_error("distribution", use.name, backend._distributions, where=use.where)
        distribution = backend._distributions[use.name]
        if use.redraw and distribution.redraw_rounds is None:
            raise ValueError(
                f"Distribution {use.name!r} has no redraw_rounds, which bound_mode: redraw needs: "
                "set how many times a value past its bound is drawn again (0: clip at once), "
                f"or write bound_mode: clip ({use.where})."
            )
        # A key that the expression does not use would be ignored: most likely a typo.
        unused = sorted(use.arguments - _names(distribution.expression))
        if unused:
            raise ValueError(
                f"{use.where}: {unused[0]} is given to distribution {use.name!r}, which does not use it."
            )


def check_rule_arguments(backend: Brian2Backend) -> None:
    """Raise if a rule is given an argument its expressions do not use."""

    table = backend.network.connections
    names = table["rule"]
    for argument, values in table.arguments("rule").items():
        rows = ~is_unset(values)
        for name in sorted(set(names[rows].tolist())):
            rule = backend._connection_rules.get(name)
            if rule is None or argument not in _names(rule.condition, rule.p, rule.n):
                first = int(np.flatnonzero(rows & (names == name))[0])
                raise ValueError(
                    f"connections.{first}: {argument} is given to rule {name!r}, which does not use "
                    "it in Brian2 (a shared rule takes no arguments)."
                )


def check_multapses(backend: Brian2Backend) -> None:
    """Raise if a rule with several synapses per pair is used without multapses."""

    table = backend.network.connections
    # Brian2 makes n synapses for each pair a project rule picks, so such a
    # rule cannot keep a connection free of multapses.
    several = [name for name, rule in backend._connection_rules.items() if rule.n != "1"]
    if several:
        rows = np.flatnonzero(np.isin(table["rule"], several) & (table["allow_multapses"] == False))  # noqa: E712
        if rows.size:
            rule = table["rule"][rows[0]]
            raise ValueError(
                f"connections.{rows[0]}: rule {rule!r} makes n = {backend._connection_rules[rule].n} synapses "
                "per pair, which allow_multapses: false does not allow."
            )


def check_delays(backend: Brian2Backend) -> None:
    """Raise if a delay can round to 0 steps (synapse models without ``on_pre`` have no delay)."""

    table = backend.network.connections
    # A synapse model without on_pre (a gap junction) has no spikes to delay.
    delayed = {name: bool(backend.synapse_model(name).on_pre) for name in set(table["synapse"].tolist())}
    has_delay = np.asarray([delayed[name] for name in table["synapse"].tolist()], dtype=bool)
    backend.network.check_shortest_delays(backend.simulation_config.resolution, has_delay)


def check_weight_units(backend: Brian2Backend) -> None:
    """Raise if a weight's ``unit`` is not that of the variable it adds to, or if
    background input or a stimulus does not go through the static synapse."""

    table = backend.network.connections
    # A weight's unit must be that of the variable it adds to (which also
    # checks that a port name is a variable of the target's model): once
    # per target, synapse, sign and unit. Weights of both signs add to two
    # variables, which only the default on_pre does.
    users = {}

    def refuse_other_than_static(user: str, synapse: str | None) -> None:
        if backend.synapse_model(synapse) is not backend.synapse_models["static_synapse"]:
            raise NotImplementedError(
                f"{user} uses synapse {synapse!r}; the Brian2 backend connects background input "
                "and stimuli only through static synapses (other synapses aren't implemented yet)."
            )

    def add_user(user: str, target: str, synapse: str | None, weight: float, both_signs: bool, unit: str) -> None:
        by_sign = backend.goes_by_sign(target, synapse, both_signs)
        if by_sign and backend.synapse_model(synapse).on_pre != models.STATIC_SYNAPSE.on_pre:
            raise ValueError(
                f"{user}: the weights can be positive and negative, and the synapse model "
                f"{backend.synapse_model(synapse).name!r} has its own on_pre, which adds to one variable. "
                "Brian2 sends each synapse to the excitatory or the inhibitory variable by its sign "
                "only with the default on_pre: give the weight a bound at 0 (lower_bound: 0 or "
                "upper_bound: 0), or the synapse a receptor_port."
            )
        for positive in (True, False) if by_sign else (weight >= 0,):
            users.setdefault((target, synapse, positive, unit), user)

    columns = (table["target"].tolist(), table["synapse"].tolist(), backend.network.expected_weights().tolist(),
               backend.weights_of_both_signs().tolist(), table["weight.unit"].tolist())
    for row, (target, *rest) in enumerate(zip(*columns)):
        add_user(f"connections.{row} ({table['source'][row]} -> {target})", target, *rest)
    for name, background in backend.network.poisson_background.items():
        weight = background.weight
        refuse_other_than_static(f"The background input of {name!r}", background.synapse)
        add_user(f"background input of {name!r}", name, background.synapse, weight.expected,
                 backend.weight_of_both_signs(weight.fields), weight.unit)
    for stimulus in backend.network.stimuli:
        if not isinstance(stimulus, DcStimulusConfig):
            weight = stimulus.weight
            refuse_other_than_static(f"The stimulus onto {stimulus.targets}", stimulus.synapse)
            for target in stimulus.targets:
                add_user(f"stimulus onto {target!r}", target, stimulus.synapse, weight.expected,
                         backend.weight_of_both_signs(weight.fields), weight.unit)
    for (target, synapse, positive, unit), user in users.items():
        variable = backend.target_variable(target, synapse, 1.0 if positive else -1.0)
        expected = backend.weight_units(target, variable)[1]
        if unit != expected:
            raise ValueError(
                f"{user}: the weight is in {unit}, but it adds to {variable!r} of the Brian2 model "
                f"{backend.neuron_model(target).name!r}, which is in {expected}."
            )


def check_final_connections(backend: Brian2Backend) -> None:
    """Raise if ``recording.final_connections`` asks for a connection without delays."""

    table = backend.network.connections
    # Saved connections are read again as a from_file row, which needs delays.
    for row in backend.simulation_config.recording.final_connection_rows(table):
        if not backend.synapse_model(table["synapse"][row]).on_pre:
            raise ValueError(
                f"recording.final_connections: connection {table['source'][row]} -> {table['target'][row]} "
                "has no delays (its synapse model has no on_pre), which a row with rule from_file needs."
            )
