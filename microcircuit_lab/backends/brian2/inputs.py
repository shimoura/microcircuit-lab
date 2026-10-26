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


def _background_variables(backend: Brian2Backend, group: _Group) -> dict[str, list[str]]:
    """The variables the group's Poisson background inputs add to, each
    with its populations."""

    variables: dict[str, list[str]] = defaultdict(list)
    for pop_name in group.populations:
        background = backend._network.poisson_background.get(pop_name)
        if background is not None:
            variable = backend._target_variable(pop_name, background.synapse, background.weight.mean)
            variables[variable].append(pop_name)
    return variables

def background_equations(backend: Brian2Backend, group: _Group) -> b2.Equations:
    """The variables of the group's Poisson background input: the weight
    ``w_background`` of each neuron's input and, for each variable it adds
    to, its mean number of spikes per step ``background_<variable>``."""

    variables = _background_variables(backend, group)
    if not variables:
        return b2.Equations("")
    units = {backend._weight_units(pops[0], variable)[0] for variable, pops in variables.items()}
    if len(units) > 1:
        raise ValueError(
            f"The background inputs of {group.populations} add to variables of different units."
        )
    lines = [f"w_background : {units.pop()} (constant)"]
    lines += [f"background_{variable} : 1 (constant)" for variable in variables]
    return b2.Equations("\n".join(lines))

def create_poisson_background(backend: Brian2Backend) -> None:
    """
    Give each configured population its background Poisson input.

    As from NEST's poisson_generator, each neuron gets its own Poisson
    number of spikes at each step, at rate x indegree,
    also for populations that share a ``generator``, each with the weight
    drawn for that neuron. One update per group and variable does this
    for all of them. The input's delay is left out: it only shifts a
    stationary Poisson train in time.
    """

    for group in backend._groups:
        variables = _background_variables(backend, group)
        if not variables:
            continue
        weights = {}
        for variable, pops in variables.items():
            rates = np.zeros(group.size)
            for pop_name in pops:
                background = backend._network.poisson_background[pop_name]
                if backend.synapse_model(background.synapse) is not backend._synapse_models["static_synapse"]:
                    raise NotImplementedError(
                        f"The background input of {pop_name!r} uses synapse {background.synapse!r}; "
                        "the Brian2 backend connects background input only through static synapses."
                    )
                start, size = group.start(pop_name), backend._network.populations[pop_name].size
                rates[start:start + size] = background.generator_rate * backend._simulation_config.resolution / 1000.0
                weight = background.weight
                mean = abs(weight.mean) if backend._weight_units(pop_name, variable)[0] == "siemens" else weight.mean
                weights[group.populations.index(pop_name)] = (mean, weight.rel_std, weight.distribution, size)
            setattr(group.neurons, f"background_{variable}", rates)
            group.neurons.run_regularly(
                f"{variable} += w_background*poisson(background_{variable})", when="synapses",
                name=f"{group.neurons.name}_background_{variable}",
            )
        unit = backend._weight_units(next(iter(variables.values()))[0], next(iter(variables)))[1]
        distributions.set_weights(
            group.neurons, "w_background", "population_index", weights, unit, backend._network.bound_mode
        )

def _stimulus_curve(backend: Brian2Backend, stimulus) -> np.ndarray:
    """
    The amplitude (pA) of a dc stimulus, or the rate (Hz) of a Poisson one,
    at every time step of the simulation, 0 outside [start, stop).
    An inhomogeneous rate holds each value until the next time, as in NEST.
    """

    dt = backend._simulation_config.resolution
    t = np.arange(int(np.ceil(backend._simulation_config.t_sim / dt)) + 1) * dt

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

    curves = [np.zeros(int(np.ceil(backend._simulation_config.t_sim / backend._simulation_config.resolution)) + 1)]
    index = {}
    for pop_name in backend._network.populations:
        dc = [
            _stimulus_curve(backend, stimulus)
            for stimulus in backend._network.stimuli
            if isinstance(stimulus, DcStimulusConfig) and pop_name in stimulus.targets
        ]
        index[pop_name] = 0
        if dc:
            index[pop_name] = len(curves)
            curves.append(np.sum(dc, axis=0))
    table = b2.TimedArray(
        np.column_stack(curves) * b2.pA, dt=backend._simulation_config.resolution * b2.ms, name="dc_current"
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
    resolution = backend._simulation_config.resolution * b2.ms

    for stimulus in backend._network.stimuli:
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
            name=f"stimulus_{backend._network.stimuli.index(stimulus)}_rate",
        )

        for target in stimulus.targets:
            size = backend._network.populations[target].size
            group = backend._group_of[target]
            name = f"stimulus_{len(backend.stimulus_generators)}"
            generator = b2.PoissonGroup(
                size, rates="stimulus_rate(t)", namespace={"stimulus_rate": rate}, name=name
            )
            backend.stimulus_generators.append(generator)
            weight, delay = stimulus.weight, stimulus.delay
            backend._make_synapses(
                generator,
                group,
                stimulus.synapse,
                backend._target_variable(target, stimulus.synapse, weight.mean),
                [({"j": f"i + {group.start(target)}"}, {})],
                f"{name}_synapses",
                "0",
                {0: (weight.mean, weight.rel_std, weight.distribution, size)},
                {0: (delay.mean, delay.rel_std, delay.distribution, delay.minimum, size)},
            )
