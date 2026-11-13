"""
Inputs of the Brian2 backend: the Poisson background and the stimuli.

Functions of ``Brian2Backend`` (``simulator.py``), kept here to keep that file
short; each takes the backend and adds the input to its groups. The background
input and the ``dc`` stimuli are part of their targets' equations and are made
with the populations; the Poisson stimuli are generators connected to their
targets.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING

import brian2 as b2
import numpy as np

from microcircuit_lab.backends.brian2 import distributions
from microcircuit_lab.config.stimuli import (
    DcStimulusConfig,
    InhomogeneousPoissonStimulusConfig,
    PoissonStimulusConfig,
)

if TYPE_CHECKING:
    from microcircuit_lab.backends.brian2.simulator import Brian2Backend, _Group

logger = logging.getLogger(__name__)


def _goes_by_sign(backend: Brian2Backend, pop_name: str) -> bool:
    """Whether the background input of a population adds to the excitatory or
    the inhibitory variable by the sign of each neuron's weight (see
    Brian2Backend.goes_by_sign)."""

    background = backend.network.poisson_background[pop_name]
    both_signs = backend.weight_of_both_signs(background.weight.fields)
    return backend.goes_by_sign(pop_name, background.synapse, both_signs)


def _background_variables(backend: Brian2Backend, group: _Group) -> tuple[dict[str, list[str]], list[str]]:
    """The variables the group's Poisson background inputs add to, each
    with its populations; and the populations whose input goes by the sign
    of each neuron's weight."""

    variables: dict[str, list[str]] = defaultdict(list)
    by_sign = []
    for pop_name in group.populations:
        background = backend.network.poisson_background.get(pop_name)
        if background is None:
            continue
        if _goes_by_sign(backend, pop_name):
            by_sign.append(pop_name)
        else:
            variable = backend.target_variable(pop_name, background.synapse, background.weight.expected)
            variables[variable].append(pop_name)
    return variables, by_sign


def _background_units(backend: Brian2Backend, group: _Group) -> tuple[str, str]:
    """The units of the weights of the group's background inputs (see
    Brian2Backend.weight_units), which must be the same for all of them."""

    variables, by_sign = _background_variables(backend, group)
    units = {backend.weight_units(pops[0], variable) for variable, pops in variables.items()}
    units |= {backend.weight_units(pop_name, backend.neuron_model(pop_name).excitatory) for pop_name in by_sign}
    if len(units) > 1:
        raise ValueError(
            f"The background inputs of {group.populations} add to variables of different units."
        )
    return units.pop()


def background_equations(backend: Brian2Backend, group: _Group) -> b2.Equations:
    """The variables of the group's Poisson background input: the weight
    ``w_background`` of each neuron's input and, for each variable it adds
    to, its mean number of spikes per step ``background_<variable>``
    (``background_by_sign`` for the inputs that go by the weight's sign)."""

    variables, by_sign = _background_variables(backend, group)
    if not variables and not by_sign:
        return b2.Equations("")
    lines = [f"w_background : {_background_units(backend, group)[0]} (constant)"]
    lines += [f"background_{variable} : 1 (constant)" for variable in variables]
    lines += ["background_by_sign : 1 (constant)"] * bool(by_sign)
    return b2.Equations("\n".join(lines))

def create_poisson_background(backend: Brian2Backend) -> None:
    """
    Give each configured population its background Poisson input.

    As from NEST's poisson_generator, each neuron gets its own Poisson
    number of spikes at each step, at rate x indegree,
    also for populations that share a ``generator``, each with the weight
    drawn for that neuron. One update per group and variable does this
    for all of them. The input's delay is left out: it only shifts a
    stationary Poisson train in time. Where the weights have both signs, a
    neuron with a positive weight gets its input on the excitatory variable
    and one with a negative weight on the inhibitory one, as in NEST.
    """

    for group in backend.groups:
        variables, by_sign = _background_variables(backend, group)
        if not variables and not by_sign:
            continue
        si_unit, unit = _background_units(backend, group)
        weights = {}

        def rates_of(pops: list[str], negate: bool) -> np.ndarray:
            """The mean number of spikes per step of each neuron of the group,
            0 outside ``pops``; also notes the weights of ``pops`` to draw."""
            rates = np.zeros(group.size)
            for pop_name in pops:
                background = backend.network.poisson_background[pop_name]
                if backend.synapse_model(background.synapse) is not backend.synapse_models["static_synapse"]:
                    raise NotImplementedError(
                        f"The background input of {pop_name!r} uses synapse {background.synapse!r}; "
                        "the Brian2 backend connects background input only through static synapses."
                    )
                start, size = group.start(pop_name), backend.network.populations[pop_name].size
                rates[start:start + size] = background.generator_rate * backend.simulation_config.resolution / 1000.0
                fields = background.weight.fields
                # A weight onto a conductance is its size, as in NEST.
                if negate and background.weight.expected < 0:
                    fields = distributions.negated(fields)
                weights[group.populations.index(pop_name)] = (fields, size)
            return rates

        for variable, pops in variables.items():
            setattr(group.neurons, f"background_{variable}", rates_of(pops, negate=si_unit == "siemens"))
            group.neurons.run_regularly(
                f"{variable} += w_background*poisson(background_{variable})", when="synapses",
                name=f"{group.neurons.name}_background_{variable}",
            )
        if by_sign:
            group.neurons.background_by_sign = rates_of(by_sign, negate=False)
            neuron = backend.neuron_model(by_sign[0])
            size = "-w_background" if si_unit == "siemens" else "w_background"
            group.neurons.run_regularly(
                f"""
                background_spikes = poisson(background_by_sign)
                {neuron.excitatory} += w_background*int(w_background >= 0*{si_unit})*background_spikes
                {neuron.inhibitory} += {size}*int(w_background < 0*{si_unit})*background_spikes
                """,
                when="synapses", name=f"{group.neurons.name}_background_by_sign",
            )
        distributions.set_drawn(group.neurons, "w_background", "population_index", weights, unit)

def _stimulus_curve(backend: Brian2Backend, stimulus) -> np.ndarray:
    """
    The amplitude (pA) of a dc stimulus, or the rate (Hz) of a Poisson one,
    at every time step of the simulation, 0 outside [start, stop).
    An inhomogeneous rate holds each value until the next time, as in NEST.
    """

    dt = backend.simulation_config.resolution
    t = np.arange(int(np.ceil(backend.simulation_config.t_sim / dt)) + 1) * dt

    if isinstance(stimulus, DcStimulusConfig):
        curve = np.full(len(t), stimulus.amplitude)
    elif isinstance(stimulus, PoissonStimulusConfig):
        curve = np.full(len(t), stimulus.rate)
    elif isinstance(stimulus, InhomogeneousPoissonStimulusConfig):
        step = np.searchsorted(stimulus.rate_times, t, side="right") - 1
        curve = np.where(step >= 0, np.asarray(stimulus.rate_values)[step.clip(0)], 0.0)
    else:
        raise ValueError(f"Unsupported stimulus type: {type(stimulus).__name__!r}")

    stop = np.inf if stimulus.stop is None else stimulus.stop
    return np.where((t >= stimulus.start) & (t < stop), curve, 0.0)

def dc_curves(backend: Brian2Backend) -> tuple[b2.TimedArray, dict[str, int]]:
    """
    The current of the dc stimuli of each population, as one table (time
    step x curve) and each population's curve in it (0: no current).
    """

    curves = [np.zeros(int(np.ceil(backend.simulation_config.t_sim / backend.simulation_config.resolution)) + 1)]
    index = {}
    for pop_name in backend.network.populations:
        dc = [
            _stimulus_curve(backend, stimulus)
            for stimulus in backend.network.stimuli
            if isinstance(stimulus, DcStimulusConfig) and pop_name in stimulus.targets
        ]
        index[pop_name] = 0
        if dc:
            index[pop_name] = len(curves)
            curves.append(np.sum(dc, axis=0))
    table = b2.TimedArray(
        np.column_stack(curves) * b2.pA, dt=backend.simulation_config.resolution * b2.ms, name="dc_current"
    )
    return table, index

def create_stimuli(backend: Brian2Backend) -> None:
    """
    Create and connect the Poisson stimuli: for each target, one Poisson
    spike train per neuron, connected with the stimulus's weight, delay and
    synapse, as from NEST's generators. ``dc`` stimuli are part of their
    targets' equations (see create_populations).
    """

    logger.info("Creating stimulus devices:")
    resolution = backend.simulation_config.resolution * b2.ms

    for stimulus in backend.network.stimuli:
        if isinstance(stimulus, DcStimulusConfig):
            continue
        logger.info(
            "Creating %s stimulus for %s (start=%g, stop=%s)",
            stimulus.type,
            stimulus.targets,
            stimulus.start,
            stimulus.stop,
        )
        rate = b2.TimedArray(
            _stimulus_curve(backend, stimulus) * b2.Hz, dt=resolution,
            name=f"stimulus_{backend.network.stimuli.index(stimulus)}_rate",
        )

        for target in stimulus.targets:
            size = backend.network.populations[target].size
            group = backend.group_of[target]
            name = f"stimulus_{len(backend.stimulus_generators)}"
            generator = b2.PoissonGroup(
                size, rates="stimulus_rate(t)", namespace={"stimulus_rate": rate}, name=name
            )
            backend.stimulus_generators.append(generator)
            weight, delay = stimulus.weight, stimulus.delay
            backend.make_synapses(
                generator,
                group,
                stimulus.synapse,
                backend.target_variable(target, stimulus.synapse, weight.expected),
                [({"j": f"i + {group.start(target)}"}, {})],
                f"{name}_synapses",
                "0",
                {0: (weight.fields, size)},
                {0: (delay.fields, size)},
                by_sign=backend.goes_by_sign(target, stimulus.synapse, backend.weight_of_both_signs(weight.fields)),
            )
