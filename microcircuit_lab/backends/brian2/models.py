"""
Neuron and synapse models, and connection rules, for the Brian2 backend.

Brian2 has no models of its own, so the project defines the ones its
``neurons.yaml`` and ``synapses.yaml`` name: as :class:`NeuronModel` and
:class:`SynapseModel` objects in the Python files of ``models/brian2/``, or in
modules given as ``model_modules``. The one model the backend has itself
is ``static_synapse``. A ``rule`` in ``connectivity.yaml`` that is not one of
the shared rules is a :class:`ConnectionRule` found the same way, and a weight
or delay ``distribution`` that is not a shared one a :class:`Distribution`.

Numbers in the config files are in NEST's units (mV, ms, pF, pA, nS, Hz), so the
same files run on both simulators; the equations are written in Brian2's units.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from microcircuit_lab.project_code import find_definitions

MODELS_FOLDER = Path("models") / "brian2"


@dataclass(frozen=True)
class NeuronModel:
    """
    A neuron model: its Brian2 equations and the variables connections add to.

    Parameters
    ----------
    name
        The name ``neurons.yaml`` gives as ``model``.
    equations
        Brian2 equations, with every parameter declared (``C_m : farad``).
        A constant input current ``I_e : amp`` is needed only where
        ``neurons.yaml`` sets it or scaling adds its compensation currents to
        it (give it a default of 0.0 then). Using ``I_stim`` in them adds the
        current of ``dc`` stimuli. For a model whose equations depend on its
        parameters, a function of the population's ``parameters`` that returns
        the equations.
    threshold, reset, refractory, method
        As for ``brian2.NeuronGroup``.
    excitatory, inhibitory
        The variable a connection adds to when its weight is positive or
        negative and its synapse has no ``receptor_port``. A conductance is
        increased by the size of the weight, as in NEST. None: such a
        connection is an error.
    receptor_port
        The variable a ``receptor_port`` adds to, with ``{port}`` in its name
        (e.g. ``"I_syn_{port}"``). None: the model has no receptor ports.
    defaults
        Values of the parameters and of the initial state for what
        ``neurons.yaml`` does not give, in NEST's units.
    """

    name: str
    equations: str | Callable[[dict[str, Any]], str]
    threshold: str
    reset: str
    excitatory: str | None = None
    inhibitory: str | None = None
    receptor_port: str | None = None
    refractory: str = "t_ref"
    method: str = "exact"
    defaults: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SynapseModel:
    """
    A synapse model: what a spike does when it arrives.

    Parameters
    ----------
    name
        The name ``synapses.yaml`` gives as ``model``.
    model
        Brian2 equations of the synapse's own variables. The weight ``w_syn`` is
        added by the backend.
    on_pre
        What a spike of the source does when it arrives: code, or a dict of
        pathway names to code (as for ``brian2.Synapses``). ``{target}``
        stands for the variable of the target neuron that the connection adds
        to, in every pathway. Can be empty, e.g. for a gap junction; then the
        connection's delay is not used.
    on_post
        What a spike of the target does at the synapse, in the same forms as
        ``on_pre``. Empty: nothing.
    delays
        For each pathway other than the main ``pre`` one, a Brian2 expression
        for its delay, e.g. ``{"slow": "delay_slow"}``. It can use the
        synapse's own variables, which are set first. The delay of the
        connection sets that of ``pre``. A pathway that on_pre and on_post do
        not have is an error.
    method
        Brian2's integration method for the equations of ``model``. None:
        Brian2 chooses.
    defaults
        Values of the synapse's variables for what ``synapses.yaml`` does not
        give, in NEST's units.
    """

    name: str
    model: str = ""
    on_pre: str | dict[str, str] = "{target} += w_syn"
    on_post: str | dict[str, str] = ""
    delays: dict[str, str] = field(default_factory=dict)
    method: str | None = None
    defaults: dict[str, Any] = field(default_factory=dict)


STATIC_SYNAPSE = SynapseModel("static_synapse")


@dataclass(frozen=True)
class ConnectionRule:
    """
    A connection rule of the project: which pairs of neurons connect.

    Parameters
    ----------
    name
        The name ``connectivity.yaml`` gives as ``rule``.
    condition, p, n
        As for ``brian2.Synapses.connect``: which pairs may connect, the
        probability that such a pair does, and how many synapses it then
        gets. Brian2 expressions, which can use the connection's
        ``parameters`` (as constants), the variables of the pre- and
        post-synaptic neurons (``V_m_pre``, ``V_m_post``), and
        ``index_pre`` / ``index_post``: each neuron's index within its
        population. A neuron is not connected to itself when the connection
        sets ``allow_autapses: false``.
    """

    name: str
    condition: str = "True"
    p: str = "1"
    n: str = "1"


@dataclass(frozen=True)
class Distribution:
    """
    A distribution of the project, for the weights or delays of connections.

    Parameters
    ----------
    name
        The name ``connectivity.yaml`` gives as a weight's or delay's
        ``distribution``.
    expression
        A Brian2 expression for each synapse's value, as a number in the
        package's units (pA or nS for a weight, ms for a delay). It can use
        the connection's ``mean`` and ``rel_std``, its ``parameters``, the
        variables of the pre- and post-synaptic neurons (``V_m_pre``), and
        ``index_pre`` / ``index_post`` (see :class:`ConnectionRule`).
    redraw_rounds
        With the network's ``bound_mode: redraw``, how many times a value
        past its bound (a weight of the other sign than ``mean``, a delay
        below the minimum) is drawn again before it is clipped to the bound.
        0 clips at once. Required with ``redraw``: how often the expression
        crosses its bound is not known here.
    """

    name: str
    expression: str
    redraw_rounds: int | None = None


#: What the project defines for Brian2, found by load_models.
KINDS = (NeuronModel, SynapseModel, ConnectionRule, Distribution)


def load_models(model_modules: Sequence[str] = ()) -> dict[type, dict[str, Any]]:
    """
    The project's definitions of each kind in :data:`KINDS`, by kind and name.

    Every one at the top level of the files in ``models/brian2/`` (of the
    folder you run from) and of the modules ``model_modules`` is found (see
    :func:`microcircuit_lab.project_code.find_definitions`). A project's own
    ``static_synapse`` replaces the backend's.
    """

    found = find_definitions(MODELS_FOLDER, "models.brian2", model_modules, KINDS)
    found[SynapseModel].setdefault(STATIC_SYNAPSE.name, STATIC_SYNAPSE)
    return found


def missing_model_error(kind: str, name: str, known: dict) -> ValueError:
    """The error for a model that ``neurons.yaml`` or ``synapses.yaml`` names,
    or a rule that ``connectivity.yaml`` names, but the project does not
    define, saying where to define it."""

    what, file, cls = {
        "neuron": ("neuron model", "neurons.yaml", "NeuronModel"),
        "synapse": ("synapse model", "synapses.yaml", "SynapseModel"),
        "rule": ("connection rule", "connectivity.yaml", "ConnectionRule"),
        "distribution": ("distribution", "connectivity.yaml", "Distribution"),
    }[kind]
    return ValueError(
        f"Brian2 has no {what} {name!r} (named in {file}). Define it as a {cls} in a file of "
        f"{MODELS_FOLDER}/ in the folder you run from (see the examples there), or in a "
        f"module passed with --model-modules. Found: {sorted(known)}."
    )
