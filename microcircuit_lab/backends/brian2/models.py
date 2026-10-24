"""
Neuron and synapse models for the Brian2 backend.

Brian2 has no models of its own, so the project defines the ones its
``neurons.yaml`` and ``synapses.yaml`` name: as :class:`NeuronModel` and
:class:`SynapseModel` objects in the Python files of ``models/brian2/``, or in
modules given as ``extension_modules``. The one model the backend has itself
is ``static_synapse``.

Numbers in the config files are in NEST's units (mV, ms, pF, pA, nS, Hz), so the
same files run on both simulators; the equations are written in Brian2's units.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from microcircuit_lab.project_code import import_folder_modules

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


def load_models(
    extension_modules: Sequence[str] = (),
) -> tuple[dict[str, NeuronModel], dict[str, SynapseModel]]:
    """
    The neuron and synapse models of the project, by name.

    Every :class:`NeuronModel` and :class:`SynapseModel` at the top level of
    the files in ``models/brian2/`` (of the folder you run from) and of the
    modules ``extension_modules`` is found. A module that fails to import
    raises. A project's own ``static_synapse`` replaces the backend's.

    Raises
    ------
    ValueError
        If two different models have the same name.
    """

    modules = list(import_folder_modules(MODELS_FOLDER, package="models.brian2").values())
    modules += [importlib.import_module(name) for name in extension_modules]

    neurons: dict[str, NeuronModel] = {}
    synapses: dict[str, SynapseModel] = {}
    for module in modules:
        for item in vars(module).values():
            if isinstance(item, NeuronModel):
                found = neurons
            elif isinstance(item, SynapseModel):
                found = synapses
            else:
                continue
            # The same object seen again, e.g. imported by another module.
            if found.get(item.name, item) is not item:
                raise ValueError(
                    f"Two Brian2 models are named {item.name!r}; the second is in {module.__name__}."
                )
            found[item.name] = item

    synapses.setdefault(STATIC_SYNAPSE.name, STATIC_SYNAPSE)
    return neurons, synapses


def missing_model_error(kind: str, name: str, known: dict) -> ValueError:
    """The error for a model that ``neurons.yaml`` or ``synapses.yaml`` names
    but the project does not define, saying where to define it."""

    return ValueError(
        f"Brian2 has no {kind} model {name!r} (named in {kind}s.yaml). Define it as a "
        f"{'NeuronModel' if kind == 'neuron' else 'SynapseModel'} in a file of "
        f"{MODELS_FOLDER}/ in the folder you run from (see the examples there), or in a "
        f"module passed with --extension-modules. Models found: {sorted(known)}."
    )
