"""
Neuron and synapse models, and connection rules, for the Brian2 backend.

Brian2 has no models of its own, so the project defines the ones its
``neurons.yaml`` and ``synapses.yaml`` name: as :class:`NeuronModel` and
:class:`SynapseModel` objects in the Python files of ``models/brian2/``, or in
modules given as ``model_modules``. The one model the backend has itself
is ``static_synapse``. A ``rule`` in ``connectivity.yaml`` that is not one of
the shared rules is a :class:`ConnectionRule` found the same way.

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
        They need an input current ``I_e : amp``, as every NEST model has:
        every population sets it, and scaling adds its compensation currents
        to it. Using ``I_stim`` in them adds the current of ``dc`` stimuli. For a
        model whose equations depend on its parameters, a function of the
        population's ``parameters`` that returns the equations.
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
        What a spike does when it arrives; ``{target}`` stands for the
        variable of the target neuron that the connection adds to.
    defaults
        Values of the synapse's variables for what ``synapses.yaml`` does not
        give, in NEST's units.
    """

    name: str
    model: str = ""
    on_pre: str = "{target} += w_syn"
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


def load_models(
    model_modules: Sequence[str] = (),
) -> tuple[dict[str, NeuronModel], dict[str, SynapseModel], dict[str, ConnectionRule]]:
    """
    The neuron and synapse models and the connection rules of the project,
    by name.

    Every :class:`NeuronModel`, :class:`SynapseModel` and
    :class:`ConnectionRule` at the top level of the files in
    ``models/brian2/`` (of the folder you run from) and of the modules
    ``model_modules`` is found (see
    :func:`microcircuit_lab.project_code.find_definitions`). A project's own
    ``static_synapse`` replaces the backend's.
    """

    kinds = (NeuronModel, SynapseModel, ConnectionRule)
    found = find_definitions(MODELS_FOLDER, "models.brian2", model_modules, kinds)
    found[SynapseModel].setdefault(STATIC_SYNAPSE.name, STATIC_SYNAPSE)
    return found[NeuronModel], found[SynapseModel], found[ConnectionRule]


def missing_model_error(kind: str, name: str, known: dict) -> ValueError:
    """The error for a model that ``neurons.yaml`` or ``synapses.yaml`` names,
    or a rule that ``connectivity.yaml`` names, but the project does not
    define, saying where to define it."""

    what, file, cls = {
        "neuron": ("neuron model", "neurons.yaml", "NeuronModel"),
        "synapse": ("synapse model", "synapses.yaml", "SynapseModel"),
        "rule": ("connection rule", "connectivity.yaml", "ConnectionRule"),
    }[kind]
    return ValueError(
        f"Brian2 has no {what} {name!r} (named in {file}). Define it as a {cls} in a file of "
        f"{MODELS_FOLDER}/ in the folder you run from (see the examples there), or in a "
        f"module passed with --model-modules. Found: {sorted(known)}."
    )
