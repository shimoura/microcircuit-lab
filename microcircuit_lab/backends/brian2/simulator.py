"""
Brian2 backend: creates and connects the network and runs the simulation.

The neuron and synapse models come from the project (``models.py``). Weights,
delays and per-neuron values are drawn in ``distributions.py``, and the pairs
of neurons that connect are picked in ``connections.py``. The background
input and stimuli are in ``inputs.py``, the recording in ``recording.py``.
Brian2 keeps the spikes in memory; they are saved as ``spikes.csv``, which ``spike_files.py``
reads without Brian2.

Brian2 spends time on every object it has, at every step and when it
generates code, so the network is made of as few objects as it can be: the
populations of one neuron model are one ``NeuronGroup`` (each a range of its
neurons), and all connections between two groups through the same synapse
are one ``Synapses``. Every object and table gets a name fixed by the
network: Brian2 puts the names in the code it generates, so a network built
again (in a sweep, or in the next run) reuses the code compiled before (with
``cpp_standalone``, when it is built in the same ``standalone_directory``).
Neurons are numbered as in NEST: population after population, from 1.
"""

from __future__ import annotations

import functools
import logging
import re
import tempfile
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import brian2 as b2
import numpy as np
from brian2.units.fundamentalunits import DIMENSIONLESS

from microcircuit_lab.backends import spikes
from microcircuit_lab.backends.brian2 import (
    connections,
    distributions,
    inputs,
    models,
    recording,
)
from microcircuit_lab.backends.statistics import log_firing_rates
from microcircuit_lab.config.connection_table import COLUMNS, given_arguments
from microcircuit_lab.config.connectivity import SHARED_RULES
from microcircuit_lab.config.distributions import (
    DelayDistribution,
    DrawnNeuronValue,
    expected_value,
    is_number_field,
)
from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.config.simulation import SimulationConfig
from microcircuit_lab.config.stimuli import (
    DcStimulusConfig,
)
from microcircuit_lab.config.synapse_files import SynapseList

logger = logging.getLogger(__name__)


def _names(*expressions: str) -> set[str]:
    """The names the Brian2 expressions use."""
    return set(re.findall(r"[A-Za-z_]\w*", " ".join(expressions)))


#: For each dimension: its name in Brian2 equations, and NEST's unit, which is
#: the unit of the numbers in the config files.
UNITS = {
    b2.volt.dim: ("volt", "mV"),
    b2.second.dim: ("second", "ms"),
    b2.farad.dim: ("farad", "pF"),
    b2.amp.dim: ("amp", "pA"),
    b2.siemens.dim: ("siemens", "nS"),
    b2.hertz.dim: ("hertz", "Hz"),
    DIMENSIONLESS: ("1", "1"),
}


def _units(dim, what: str) -> tuple[str, str]:
    """The name in equations and NEST's unit of the dimension of ``what``."""

    if dim not in UNITS:
        raise ValueError(
            f"{what} has the unit {b2.get_unit(dim)}; the config files give values only "
            "in mV, ms, pF, pA, nS, Hz or without a unit."
        )
    return UNITS[dim]


@functools.cache
def _equations(text: str) -> b2.Equations:
    """A model's equations, parsed once per text: they are looked up for every
    connection onto the model."""
    return b2.Equations(text)


def _by_port(parameters: dict) -> dict:
    """The parameters, with a list (e.g. ``tau_syn: [0.5, 2.0]``) given as one
    value per receptor port (``tau_syn_1``, ``tau_syn_2``)."""

    values = {}
    for name, value in parameters.items():
        if isinstance(value, list):
            values.update({f"{name}_{port}": item for port, item in enumerate(value, start=1)})
        else:
            values[name] = value
    return values


@dataclass
class _Group:
    """The populations that share one Brian2 NeuronGroup, in order."""

    model: models.NeuronModel
    equations: b2.Equations
    populations: list[str] = field(default_factory=list)
    starts: list[int] = field(default_factory=list)
    size: int = 0
    neurons: b2.NeuronGroup | None = None

    def start(self, population: str) -> int:
        return self.starts[self.populations.index(population)]


class Brian2Backend:
    """Builds the network in Brian2, runs it and reads back the spikes."""

    def __init__(
        self,
        network: NetworkConfig,
        simulation_config: SimulationConfig,
        *,
        device: Literal["runtime", "cpp_standalone"] = "runtime",
        codegen_target: Literal["auto", "cython", "numpy"] = "auto",
        standalone_directory: str | Path | None = None,
        extensions: Sequence[str] = (),
    ) -> None:
        """
        Parameters
        ----------
        network, simulation_config
            The network and the simulation settings.
        device
            ``"runtime"`` runs the network from Python; ``"cpp_standalone"``
            compiles it to C++ and runs it with ``local_num_threads`` OpenMP
            threads.
        codegen_target
            How the runtime device runs the network's code: Brian2's default
            ``"auto"`` compiles it with Cython (or uses numpy if there is no
            compiler). Compiling takes a while the first time a kind of
            network runs, and is kept for later runs; ``"numpy"`` compiles
            nothing, so it starts at once but runs slower.
        standalone_directory
            Where ``"cpp_standalone"`` writes and compiles the network's C++
            code. A folder kept from run to run lets Brian2 compile only what
            changed; two runs at the same time must not share it. None: a new
            temporary folder at each run, so all is compiled again.
        extensions
            Python modules that define neuron and synapse models, besides the
            files in ``extensions/brian2/`` of the folder you run from.
        """

        if device not in ("runtime", "cpp_standalone"):
            raise ValueError(f"Unknown Brian2 device {device!r}; use 'runtime' or 'cpp_standalone'.")
        if standalone_directory is not None and device != "cpp_standalone":
            raise ValueError("Brian2's standalone_directory is used only with device: cpp_standalone.")
        if codegen_target not in ("auto", "cython", "numpy"):
            raise ValueError(
                f"Unknown Brian2 codegen_target {codegen_target!r}; use 'auto', 'cython' or 'numpy'."
            )

        self.network = network
        self.simulation_config = simulation_config
        self._device = device
        self._codegen_target = codegen_target
        self._standalone_directory = standalone_directory
        self._extensions = extensions
        self._rng = np.random.default_rng(simulation_config.rng_seed)
        self._standalone_dir: tempfile.TemporaryDirectory | None = None
        self._neuron_models: dict[str, models.NeuronModel] = {}
        self.synapse_models: dict[str, models.SynapseModel] = {}
        self._connection_rules: dict[str, models.ConnectionRule] = {}
        self._distributions: dict[str, models.Distribution] = {}
        self._checked = False
        self._forget_build()

    def _forget_build(self) -> None:
        """No Brian2 objects: before the first build, and at the start of each
        build, so that a second one does not reuse those of the first."""

        self.groups: list[_Group] = []
        self.group_of: dict[str, _Group] = {}
        #: Each population as a Brian2 subgroup of its NeuronGroup.
        self.populations: dict[str, b2.Subgroup] = {}
        self.first_ids: dict[str, int] = {}
        self.stimulus_generators: list[b2.PoissonGroup] = []
        self.synapses: list[b2.Synapses] = []
        #: For each row of the connection table, where its synapses are: their
        #: Synapses, the first and the number of its source and target neurons
        #: there, and the factor that gives the weight as written (-1 for an
        #: inhibitory conductance, which Brian2 holds as its size).
        self._synapses_of_row: dict[int, tuple] = {}
        self.spike_recorders: list[tuple[_Group, b2.SpikeMonitor]] = []
        #: The monitors of each recorded variable: one per group.
        self.multimeters: dict[str, list[tuple[_Group, b2.StateMonitor]]] = {}
        self.cached_spikes: tuple[np.ndarray, np.ndarray] | None = None

    def version(self) -> str:
        return b2.__version__

    def num_processes(self) -> int:
        return 1

    def rank(self) -> int:
        return 0

    def sync_processes(self) -> None:
        pass

    def prepare_output(self, run_dir: Path) -> None:
        """
        Nothing to set up: Brian2 keeps the recordings in memory, and
        save_recordings() writes them.
        """

    def initialize(self) -> None:
        """
        Reset Brian2 and set the device, the time step and the seed.
        """

        # Brian2 keeps its device between networks: reset it, so that a second
        # build in the same Python process starts afresh.
        b2.device.reinit()
        b2.device.activate()
        self._forget_build()

        if self._device == "cpp_standalone":
            directory = self._standalone_directory
            if directory is None:
                # A second build gets a new folder: delete the first one now,
                # not when Python exits. The last one is deleted when this
                # backend is, after its recordings have been read.
                if self._standalone_dir is not None:
                    self._standalone_dir.cleanup()
                self._standalone_dir = tempfile.TemporaryDirectory(prefix="brian2_standalone_")
                directory = self._standalone_dir.name
            b2.set_device("cpp_standalone", directory=str(directory), build_on_run=True)
            b2.prefs.devices.cpp_standalone.openmp_threads = self.simulation_config.local_num_threads
        else:
            if self.simulation_config.local_num_threads > 1:
                logger.warning(
                    "Brian2's runtime device runs on one thread; local_num_threads=%d is used "
                    "only with the cpp_standalone device.",
                    self.simulation_config.local_num_threads,
                )
            b2.set_device("runtime")
            b2.prefs.codegen.target = self._codegen_target

        b2.defaultclock.dt = self.simulation_config.resolution * b2.ms
        b2.seed(self.simulation_config.rng_seed)
        self._rng = np.random.default_rng(self.simulation_config.rng_seed)

    def check(self) -> None:
        """
        Find the project's models, connection rules and distributions, and
        raise if a population, a ``synapses.yaml`` entry or a connection names
        one that is not defined, if a distribution's ``redraw_rounds`` is
        needed but not set, if a rule or distribution is given an argument
        its expressions do not use (a shared rule uses none), if a project
        rule with several synapses per pair is used without multapses, or if
        a weight's ``unit`` is not that of the variable it adds to.
        """

        found = models.load_models(self._extensions)
        self._neuron_models = found[models.NeuronModel]
        self.synapse_models = found[models.SynapseModel]
        self._connection_rules = found[models.ConnectionRule]
        self._distributions = found[models.Distribution]
        for population in self.network.populations:
            self.neuron_model(population)
        for synapse in self.network.synapses:
            self.synapse_model(synapse)

        table = self.network.connections
        for name in sorted(set(table["rule"][~np.isin(table["rule"], SHARED_RULES)].tolist())):
            if name not in self._connection_rules:
                raise models.missing_model_error("rule", name, self._connection_rules)
        for use in self.network.distributions_not_shared():
            if use.name not in self._distributions:
                raise models.missing_model_error("distribution", use.name, self._distributions, where=use.where)
            distribution = self._distributions[use.name]
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
        names = table["rule"]
        for argument, values in table.arguments("rule").items():
            rows = ~np.isnan(values)
            for name in sorted(set(names[rows].tolist())):
                rule = self._connection_rules.get(name)
                if rule is None or argument not in _names(rule.condition, rule.p, rule.n):
                    first = int(np.flatnonzero(rows & (names == name))[0])
                    raise ValueError(
                        f"connections.{first}: {argument} is given to rule {name!r}, which does not use "
                        "it in Brian2 (a shared rule takes no arguments)."
                    )

        # Brian2 makes n synapses for each pair a project rule picks, so such a
        # rule cannot keep a connection free of multapses.
        several = [name for name, rule in self._connection_rules.items() if rule.n != "1"]
        if several:
            rows = np.flatnonzero(np.isin(table["rule"], several) & (table["allow_multapses"] == False))  # noqa: E712
            if rows.size:
                rule = table["rule"][rows[0]]
                raise ValueError(
                    f"connections.{rows[0]}: rule {rule!r} makes n = {self._connection_rules[rule].n} synapses "
                    "per pair, which allow_multapses: false does not allow."
                )

        # A fixed delay rounds to a whole number of steps. NEST refuses one that
        # rounds to 0 (below half a step); Brian2 would deliver the spike in the
        # same step. A drawn delay is kept at its lower_bound or more.
        shortest = 0.5 * self.simulation_config.resolution
        # A synapse model without on_pre (a gap junction) has no spikes to delay.
        delayed = {name: bool(self.synapse_model(name).on_pre) for name in set(table["synapse"].tolist())}
        has_delay = np.asarray([delayed[name] for name in table["synapse"].tolist()], dtype=bool)
        fixed = np.asarray([name is None for name in table["delay.distribution"]], dtype=bool)
        smallest = np.where(fixed, table["delay.value"], table["delay.lower_bound"])
        from_file = table["rule"] == "from_file"
        for row in np.flatnonzero(from_file):
            smallest[row] = self.network.synapse_lists[table["file"][row]].delay.min()
        too_short = has_delay & (smallest < shortest)
        if too_short.any():
            row = int(np.flatnonzero(too_short)[0])
            what = "shortest delay in its file" if from_file[row] else "fixed delay" if fixed[row] else "delay's lower_bound"
            raise ValueError(
                f"connections.{row} ({table['source'][row]} -> {table['target'][row]}): the {what} "
                f"{smallest[row]} ms is below half the resolution ({shortest} ms), so a delay "
                f"rounds to 0; use at least {shortest} ms."
            )
        delays = [(f"background input of {name!r}", b.delay) for name, b in self.network.poisson_background.items()]
        delays += [
            (f"stimulus onto {target!r}", stimulus.delay)
            for stimulus in self.network.stimuli
            if not isinstance(stimulus, DcStimulusConfig)
            for target in stimulus.targets
        ]
        for user, delay in delays:
            smallest = delay.value if delay.distribution is None else delay.lower_bound
            if smallest < shortest:
                raise ValueError(
                    f"{user}: the delay {'' if delay.distribution is None else 'lower_bound '}{smallest} ms "
                    f"is below half the resolution ({shortest} ms), so a delay rounds to 0; use at least "
                    f"{shortest} ms."
                )

        # A weight's unit must be that of the variable it adds to (which also
        # checks that a port name is a variable of the target's model): once
        # per target, synapse, sign and unit. Weights of both signs add to two
        # variables, which only the default on_pre does.
        users = {}

        def add_user(user: str, target: str, synapse: str | None, weight: float, both_signs: bool, unit: str) -> None:
            by_sign = self.goes_by_sign(target, synapse, both_signs)
            if by_sign and self.synapse_model(synapse).on_pre != models.STATIC_SYNAPSE.on_pre:
                raise ValueError(
                    f"{user}: the weights can be positive and negative, and the synapse model "
                    f"{self.synapse_model(synapse).name!r} has its own on_pre, which adds to one variable. "
                    "Brian2 sends each synapse to the excitatory or the inhibitory variable by its sign "
                    "only with the default on_pre: give the weight a bound at 0 (lower_bound: 0 or "
                    "upper_bound: 0), or the synapse a receptor_port."
                )
            for positive in (True, False) if by_sign else (weight >= 0,):
                users.setdefault((target, synapse, positive, unit), user)

        columns = (table["target"].tolist(), table["synapse"].tolist(), self.network.expected_weights().tolist(),
                   self.weights_of_both_signs().tolist(), table["weight.unit"].tolist())
        for row, (target, *rest) in enumerate(zip(*columns)):
            add_user(f"connections.{row} ({table['source'][row]} -> {target})", target, *rest)
        for name, background in self.network.poisson_background.items():
            weight = background.weight
            add_user(f"background input of {name!r}", name, background.synapse, weight.expected,
                     self.weight_of_both_signs(weight.fields), weight.unit)
        for stimulus in self.network.stimuli:
            if not isinstance(stimulus, DcStimulusConfig):
                weight = stimulus.weight
                for target in stimulus.targets:
                    add_user(f"stimulus onto {target!r}", target, stimulus.synapse, weight.expected,
                             self.weight_of_both_signs(weight.fields), weight.unit)
        for (target, synapse, positive, unit), user in users.items():
            variable = self.target_variable(target, synapse, 1.0 if positive else -1.0)
            expected = self.weight_units(target, variable)[1]
            if unit != expected:
                raise ValueError(
                    f"{user}: the weight is in {unit}, but it adds to {variable!r} of the Brian2 model "
                    f"{self.neuron_model(target).name!r}, which is in {expected}."
                )
        self._checked = True

    def build(self) -> None:
        """
        Build the complete network. It calls :meth:`check` first if it has
        not run yet, so a backend used without ``Simulation`` also fails
        before building.
        """

        if not self._checked:
            self.check()
        self.initialize()

        self.create_populations()

        if self.simulation_config.recording.spike_recording:
            self.create_spike_recorders()

        if self.simulation_config.recording.variables:
            self.create_multimeters()

        self.create_poisson_background()

        if self.network.stimuli:
            self.create_stimuli()

        self.create_connections()

    def neuron_model(self, population: str) -> models.NeuronModel:
        """The Brian2 model of a population."""

        name = self.network.populations[population].neuron.model
        if name not in self._neuron_models:
            raise models.missing_model_error("neuron", name, self._neuron_models)
        return self._neuron_models[name]

    def _equations_text(self, population: str) -> str:
        """The equations of a population's model, for its parameters if they
        depend on them."""

        model = self.neuron_model(population)
        if callable(model.equations):
            return model.equations(dict(self.network.populations[population].neuron.parameters))
        return model.equations

    def synapse_model(self, synapse: str | None) -> models.SynapseModel:
        """The Brian2 model of a synapses.yaml entry (None: static_synapse)."""

        name = models.STATIC_SYNAPSE.name if synapse is None else self.network.synapses[synapse].model
        if name not in self.synapse_models:
            raise models.missing_model_error("synapse", name, self.synapse_models)
        return self.synapse_models[name]

    def create_populations(self) -> None:
        """
        Create all neuron populations: one NeuronGroup for the populations of
        each neuron model (and of each set of equations, for a model whose
        equations depend on its parameters).

        Every neuron knows its ``population_index`` in its group, and its
        ``index`` within its population (for connection rules). A group with
        ``dc`` stimuli reads its current from one table of all their currents,
        at each neuron's ``dc_index``. A group with Poisson background input
        has the variables of that input (see create_poisson_background).
        """

        by_equations: dict[tuple[str, str], _Group] = {}
        values: dict[str, dict] = {}
        for pop_name, pop_cfg in self.network.populations.items():
            model = self.neuron_model(pop_name)
            parameters = dict(pop_cfg.neuron.parameters)
            equations = b2.Equations(self._equations_text(pop_name))

            values[pop_name] = {**model.defaults, **_by_port(parameters), **pop_cfg.initial_state}
            missing = sorted(set(equations.parameter_names) - set(values[pop_name]) - {"I_stim"})
            if missing:
                raise ValueError(
                    f"The Brian2 model {model.name!r} of {pop_name!r} needs {missing}: give "
                    "them in neurons.yaml or in the model's defaults."
                )
            unknown = sorted(set(values[pop_name]) - set(equations.names))
            if unknown:
                raise ValueError(
                    f"{pop_name!r} (neurons.yaml) sets {unknown}, which its Brian2 model "
                    f"{model.name!r} does not have; it has {sorted(equations.names)}."
                    + (" I_e can also be a constant current written by a builder "
                       "(scaling, replace_background_by_mean_current)." if "I_e" in unknown else "")
                )

            group = by_equations.setdefault((model.name, str(equations)), _Group(model, equations))
            group.populations.append(pop_name)
            group.starts.append(group.size)
            group.size += pop_cfg.size
            self.group_of[pop_name] = group
        self.groups = list(by_equations.values())

        first_id = 1
        for pop_name, pop_cfg in self.network.populations.items():
            self.first_ids[pop_name] = first_id
            first_id += pop_cfg.size

        dc_curves, dc_index = inputs.dc_curves(self)
        for group in self.groups:
            logger.info(
                "Creating %s (%d neurons, model %s)", ", ".join(group.populations), group.size, group.model.name
            )
            equations = group.equations + b2.Equations(
                "population_index : integer (constant)\nindex : integer (constant)"
            )
            namespace = {}
            has_dc = any(dc_index[pop] for pop in group.populations)
            if "I_stim" in group.equations.identifiers:
                if has_dc:
                    namespace["dc_current"] = dc_curves
                    equations += b2.Equations("dc_index : integer (constant)\nI_stim = dc_current(t, dc_index) : amp")
                else:
                    equations += b2.Equations("I_stim = 0*amp : amp")
            elif has_dc:
                raise ValueError(
                    f"{[pop for pop in group.populations if dc_index[pop]]} get a dc stimulus, but their "
                    f"Brian2 model {group.model.name!r} has no I_stim in its equations."
                )
            equations += inputs.background_equations(self, group)

            neurons = b2.NeuronGroup(
                group.size,
                equations,
                threshold=group.model.threshold,
                reset=group.model.reset,
                refractory=group.model.refractory,
                method=group.model.method,
                namespace=namespace,
                name=f"group_{self.groups.index(group)}",
            )
            group.neurons = neurons
            sizes = [self.network.populations[pop].size for pop in group.populations]
            neurons.population_index = np.repeat(np.arange(len(group.populations)), sizes)
            neurons.index = np.concatenate([np.arange(size) for size in sizes])
            self._set_group_values(group, values)
            if has_dc:
                neurons.dc_index = np.repeat(
                    [dc_index[pop] for pop in group.populations],
                    [self.network.populations[pop].size for pop in group.populations],
                )
            for pop_name, start in zip(group.populations, group.starts):
                self.populations[pop_name] = neurons[start:start + self.network.populations[pop_name].size]

    def _set_group_values(self, group: _Group, values: dict[str, dict]) -> None:
        """Set the parameters and initial state of a group's neurons, given in
        the package's units, one variable at a time for all its populations:
        numbers as one array; a variable that some population draws per
        neuron is drawn by Brian2 (distributions.set_drawn), as weights are,
        from the entry of each neuron's population."""

        sizes = [self.network.populations[pop].size for pop in group.populations]
        for name in sorted({name for pop in group.populations for name in values[pop]}):
            unit = _units(group.neurons.variables[name].dim, f"{name!r} of {group.model.name!r}")[1]
            # A population that does not set the variable keeps 0, where Brian2 starts it (the
            # values cannot be read before the run in C++ standalone mode).
            given = [values[pop].get(name, 0.0) for pop in group.populations]
            if any(isinstance(value, DrawnNeuronValue) for value in given):
                entries = {
                    k: (value.fields if isinstance(value, DrawnNeuronValue) else distributions.fixed(value), sizes[k])
                    for k, value in enumerate(given)
                }
                projects = {k: self._distributions[fields["distribution"]] for k, (fields, _) in entries.items()
                            if fields["distribution"] in self._distributions}
                distributions.set_drawn(group.neurons, name, "population_index", entries, unit, projects)
                continue
            array = np.repeat(given, sizes)
            setattr(group.neurons, name, array * getattr(b2, unit, 1))

    def _set_values(self, target, equations: b2.Equations, values: dict, where: str) -> None:
        """Set the variables of synapses, given in the package's units."""

        for name, value in values.items():
            if name not in equations.names:
                raise ValueError(
                    f"{where} sets {name!r}, which its Brian2 model does not have; "
                    f"it has {sorted(equations.names)}."
                )
            unit = _units(target.variables[name].dim, f"{name!r} of {where}")[1]
            setattr(target, name, value * getattr(b2, unit, 1))

    def target_variable(self, target: str, synapse: str | None, weight: float) -> str:
        """
        The variable of the target population that a connection adds to: the
        one of its synapse's receptor port (a port name is the variable), or
        else the model's excitatory or inhibitory one, as the weight's sign
        says (as in NEST).
        """

        model = self.neuron_model(target)
        port = self.network.receptor_port(synapse)
        if isinstance(port, str):
            names = _equations(self._equations_text(target)).names
            if port not in names:
                raise ValueError(
                    f"Synapse {synapse!r} sets receptor_port {port!r}, but the Brian2 model "
                    f"{model.name!r} of {target!r} has no variable of that name; "
                    f"it has {sorted(names)}."
                )
            return port
        if port is not None:
            if model.receptor_port is None:
                raise ValueError(
                    f"Synapse {synapse!r} sets receptor_port {port}, but the Brian2 model "
                    f"{model.name!r} of {target!r} has no receptor ports."
                )
            return model.receptor_port.format(port=port)

        variable = model.excitatory if weight >= 0 else model.inhibitory
        if variable is None:
            raise ValueError(
                f"The Brian2 model {model.name!r} of {target!r} needs a receptor_port in "
                "synapses.yaml for each connection to it."
            )
        return variable

    def weights_of_both_signs(self) -> np.ndarray:
        """Which connections can have positive and negative weights (see
        distributions.both_signs); for rule from_file, whether its file has both."""

        table = self.network.connections
        both = distributions.both_signs({name: table[f"weight.{name}"] for name in DelayDistribution.model_fields})
        for row in np.flatnonzero(table["rule"] == "from_file"):
            weight = self.network.synapse_lists[table["file"][row]].weight
            both[row] = (weight > 0).any() and (weight < 0).any()
        return both

    def weight_of_both_signs(self, fields: dict) -> bool:
        """:meth:`weights_of_both_signs` for one weight, from its fields."""
        return bool(distributions.both_signs({
            name: np.array([fields[name]], dtype=float if is_number_field(name) else object)
            for name in DelayDistribution.model_fields
        })[0])

    def goes_by_sign(self, target: str, synapse: str | None, both_signs: bool) -> bool:
        """
        Whether each synapse of a connection adds to the excitatory or the
        inhibitory variable of ``target`` by its own sign, as in NEST: its
        weights have both signs, its synapse has no receptor port, and the
        model has a variable for each. Any other connection adds to one
        variable (see :meth:`target_variable`).
        """

        model = self.neuron_model(target)
        return bool(both_signs) and self.network.receptor_port(synapse) is None and model.excitatory != model.inhibitory

    def weight_units(self, target: str, variable: str) -> tuple[str, str]:
        """The units of the weights onto ``variable`` of ``target``: its name in
        equations and the package's unit (pA for a current, nS for a
        conductance, mV for a voltage)."""

        equations = _equations(self._equations_text(target))
        if variable not in equations.names:
            raise ValueError(
                f"The Brian2 model {self.neuron_model(target).name!r} of {target!r} has no "
                f"variable {variable!r} for its connections to add to."
            )
        return _units(equations[variable].dim, f"{variable!r} of {target!r}")

    def make_synapses(
        self,
        source: b2.Group,
        target: _Group,
        synapse: str | None,
        variable: str,
        calls: list[tuple[dict, dict]],
        name: str,
        index: str,
        weights: dict[int, tuple],
        delays: dict[int, tuple],
        projects: dict[str, dict] | None = None,
        synapse_list: SynapseList | None = None,
        by_sign: bool = False,
    ) -> None:
        """
        One Brian2 ``Synapses`` from ``source`` to the group ``target``, onto
        ``variable``, through the model of ``synapse``: made by the
        ``connect`` calls ``calls`` (see connections.connect_calls), named
        ``name``, with the
        weights and delays of each entry by ``index`` (see
        distributions.set_drawn), from a project distribution for the entries
        in ``projects["weight"]`` / ``projects["delay"]``; or, with
        ``synapse_list`` (a connection from a file, made by one call), the
        weight and delay of each synapse in its file. A weight onto a
        conductance is its size, as in NEST. With ``by_sign`` (see
        :meth:`goes_by_sign`), a synapse with a positive weight adds to the
        excitatory variable and one with a negative weight to the inhibitory
        one, and the weights keep their sign.
        """

        projects = projects or {"weight": {}, "delay": {}}

        si_unit, unit = self.weight_units(target.populations[0], variable)
        model = self.synapse_model(synapse)

        def code(on):
            if isinstance(on, dict):
                return {k: v.format(target=f"{variable}_post") for k, v in on.items()}
            return on.format(target=f"{variable}_post")

        on_pre = code(model.on_pre)
        if by_sign:
            neuron = self.neuron_model(target.populations[0])
            size = "-w_syn" if si_unit == "siemens" else "w_syn"
            on_pre = (
                f"{neuron.excitatory}_post += w_syn*int(w_syn >= 0*{si_unit})\n"
                f"{neuron.inhibitory}_post += {size}*int(w_syn < 0*{si_unit})"
            )

        pathways = {
            *(model.on_pre if isinstance(model.on_pre, dict) else ["pre"] * bool(model.on_pre)),
            *(model.on_post if isinstance(model.on_post, dict) else ["post"] * bool(model.on_post)),
        }
        if isinstance(model.on_pre, dict) and "pre" not in model.on_pre:
            raise ValueError(
                f"Synapse model {model.name!r} has on_pre pathways {sorted(model.on_pre)}; one must be "
                "named 'pre', which gets the delays of connectivity.yaml (set the others in delays)."
            )
        for pathway in model.delays:
            if pathway not in pathways:
                raise ValueError(
                    f"Synapse model {model.name!r} sets a delay for pathway {pathway!r}, "
                    f"which its on_pre and on_post do not have; they have {sorted(pathways)}."
                )
        options = {} if model.method is None else {"method": model.method}
        synapses = b2.Synapses(
            source,
            target.neurons,
            model=f"w_syn : {si_unit}\n{model.model}",
            on_pre=on_pre,
            on_post=code(model.on_post) or None,
            namespace={},
            name=name,
            **options,
        )
        for arguments, namespace in calls:
            synapses.connect(**arguments, namespace=namespace)

        if synapse_list is not None:
            weight = np.abs(synapse_list.weight) if si_unit == "siemens" and not by_sign else synapse_list.weight
            synapses.w_syn[:] = weight * getattr(b2, unit, 1)
            if "pre" in pathways:
                synapses.delay[:] = synapse_list.delay * b2.ms
        if si_unit == "siemens" and synapse_list is None and not by_sign:
            for k, (fields, number) in weights.items():
                if expected_value(fields) < 0:
                    weights[k] = (distributions.negated(fields), number)
                    # A project distribution's own draw is negated, with the fields as given.
                    if k in projects["weight"]:
                        projects["weight"][k] = distributions.negated_draw(projects["weight"][k], fields)
        if synapse_list is None:
            distributions.set_drawn(synapses, "w_syn", index, weights, unit, projects["weight"])
            if "pre" in pathways:  # a gap junction has no pathway of spikes to delay
                distributions.set_drawn(synapses, "delay", index, delays, "ms", projects["delay"])

        parameters = {} if synapse is None else self.network.synapses[synapse].parameters
        self._set_values(
            synapses,
            b2.Equations(model.model),
            {**model.defaults, **parameters},
            f"synapse {synapse or model.name!r} (synapses.yaml)",
        )
        for pathway, expression in model.delays.items():
            getattr(synapses, pathway).delay = expression
        self.synapses.append(synapses)

    def create_connections(self) -> None:
        """
        Connect populations according to the connectivity configuration:
        one Brian2 ``Synapses`` for all rows of the connection table between
        two groups, through the same synapse, onto the same variable. Rows
        between the same two populations go into different ones, since a
        synapse's weight and delay are read by its pair of populations.
        """

        logger.info("Creating recurrent connections:")

        table = self.network.connections
        column = {name: table[name].tolist() for name in COLUMNS}
        arguments = {
            group: {name: values.tolist() for name, values in table.arguments(group).items()}
            for group in ("rule", "weight", "delay")
        }

        def given(group: str, row: int) -> dict:
            return given_arguments({name: values[row] for name, values in arguments[group].items()})

        weight = self.network.expected_weights().tolist()
        both_signs = self.weights_of_both_signs().tolist()
        objects: dict[tuple, list[int]] = defaultdict(list)
        seen: dict[tuple, int] = defaultdict(int)
        for row in range(len(table)):
            source, target, synapse = column["source"][row], column["target"][row], column["synapse"][row]
            variable = self.target_variable(target, synapse, weight[row])
            by_sign = self.goes_by_sign(target, synapse, both_signs[row])
            key = (id(self.group_of[source]), id(self.group_of[target]), synapse, variable, by_sign)
            if column["rule"][row] == "from_file":
                # A Synapses of its own, whose synapses are those of the file, in its order.
                objects[(*key, ("from_file", row))].append(row)
                continue
            pair = (*key, source, target)
            objects[(*key, seen[pair])].append(row)
            seen[pair] += 1

        for (_, _, synapse, variable, by_sign, _), rows in objects.items():
            source = self.group_of[column["source"][rows[0]]]
            target = self.group_of[column["target"][rows[0]]]
            if column["rule"][rows[0]] == "from_file":
                row = rows[0]
                synapse_list = self.network.synapse_lists[column["file"][row]]
                calls = [({"i": synapse_list.source_index + source.start(column["source"][row]),
                           "j": synapse_list.target_index + target.start(column["target"][row])}, {})]
                self.make_synapses(
                    source.neurons, target, synapse, variable, calls, f"synapses_{len(self.synapses)}",
                    "0", {}, {}, synapse_list=synapse_list, by_sign=by_sign,
                )
                self._remember_rows(rows, column, source, target, variable, weight, by_sign)
                continue
            placed = [
                connections.Row(
                    rule=column["rule"][row],
                    number=column["number"][row],
                    source_start=source.start(column["source"][row]),
                    source_size=self.network.populations[column["source"][row]].size,
                    target_start=target.start(column["target"][row]),
                    target_size=self.network.populations[column["target"][row]].size,
                    autapses=True if column["allow_autapses"][row] is None else bool(column["allow_autapses"][row]),
                    multapses=True if column["allow_multapses"][row] is None else bool(column["allow_multapses"][row]),
                    same_population=column["source"][row] == column["target"][row],
                    arguments=given("rule", row),
                    definition=self._connection_rules.get(column["rule"][row]),
                )
                for row in rows
            ]
            name = f"synapses_{len(self.synapses)}"
            calls, numbers = connections.connect_calls(placed, source.size, target.size, self._rng, name)

            n_target = len(target.populations)
            weights, delays = {}, {}
            projects: dict[str, dict] = {"weight": {}, "delay": {}}
            for row, number in zip(rows, numbers):
                pair = (
                    source.populations.index(column["source"][row]) * n_target
                    + target.populations.index(column["target"][row])
                )
                for what, entries in (("weight", weights), ("delay", delays)):
                    fields = {name: column[f"{what}.{name}"][row] for name in DelayDistribution.model_fields}
                    fields |= given(what, row)
                    entries[pair] = (fields, number)
                    distribution = self._distributions.get(fields["distribution"])
                    if distribution is not None:
                        projects[what][pair] = distribution
            self.make_synapses(
                source.neurons, target, synapse, variable, calls, name,
                f"population_index_pre*{n_target} + population_index_post", weights, delays, projects,
                by_sign=by_sign,
            )
            self._remember_rows(rows, column, source, target, variable, weight, by_sign)

    def _remember_rows(self, rows, column, source, target, variable, weight, by_sign) -> None:
        """Where the synapses of ``rows`` are, in the Synapses just made (see
        ``_synapses_of_row``)."""

        conductance = self.weight_units(target.populations[0], variable)[0] == "siemens"
        for row in rows:
            source_name, target_name = column["source"][row], column["target"][row]
            self._synapses_of_row[row] = (
                self.synapses[-1],
                source.start(source_name), self.network.populations[source_name].size,
                target.start(target_name), self.network.populations[target_name].size,
                -1.0 if conductance and weight[row] < 0 and not by_sign else 1.0,
            )

    def final_connections(self, rows: list[int]) -> dict[int, SynapseList]:
        """
        The synapses of these rows of the connection table at the end of the
        run (see SimulationBackend.final_connections), read from Brian2.
        """

        table = self.network.connections
        synapse_lists = {}
        for row in rows:
            synapses, source_start, n_source, target_start, n_target, sign = self._synapses_of_row[row]
            if not hasattr(synapses, "pre"):
                raise ValueError(
                    f"recording.final_connections: connection {table['source'][row]} -> {table['target'][row]} "
                    "has no delays (its synapse model has no on_pre), which a row with rule from_file needs."
                )
            i, j = np.asarray(synapses.i[:]), np.asarray(synapses.j[:])
            here = (i >= source_start) & (i < source_start + n_source) & (j >= target_start) & (j < target_start + n_target)
            unit = getattr(b2, table["weight.unit"][row])
            synapse_lists[row] = SynapseList(
                source_index=i[here].astype(np.int64) - source_start,
                target_index=j[here].astype(np.int64) - target_start,
                weight=sign * np.asarray(synapses.w_syn[:][here] / unit),
                delay=np.asarray(synapses.delay[:][here] / b2.ms),
            )
        return synapse_lists

    def get_population(self, name: str) -> np.ndarray:
        """
        The node IDs of a population.
        """

        first_id = self.first_ids[name]
        return np.arange(first_id, first_id + self.network.populations[name].size)

    def create_spike_recorders(self) -> None:
        """
        Create one spike monitor per group.
        """

        recording.create_spike_recorders(self)

    def create_multimeters(self) -> None:
        """
        Create, for each variable of ``recording.variables``, one state monitor
        per group: of the first ``sample_size`` neurons (all, if not set) of
        the populations the variable is recorded from.
        """

        recording.create_multimeters(self)

    def create_poisson_background(self) -> None:
        """
        Give each configured population its background Poisson input (see
        ``inputs.py``).
        """

        inputs.create_poisson_background(self)

    def create_stimuli(self) -> None:
        """
        Create and connect the Poisson stimuli (see ``inputs.py``). ``dc``
        stimuli are part of their targets' equations (see create_populations).
        """

        inputs.create_stimuli(self)

    def simulate(self) -> None:
        """
        Run the simulation, discarding any spike events cached from before it.
        """

        network = b2.Network(
            *(group.neurons for group in self.groups),
            *self.stimulus_generators,
            *self.synapses,
            *(monitor for _, monitor in self.spike_recorders),
            *(monitor for monitors in self.multimeters.values() for _, monitor in monitors),
        )
        network.run(self.simulation_config.t_sim * b2.ms)
        self.cached_spikes = None

    def print_statistics(self) -> None:
        """
        Print simple statistics.
        """

        logger.info("")
        logger.info("Simulation statistics")
        logger.info("---------------------")

        if not self.spike_recorders:
            return

        log_firing_rates(
            logger,
            self.get_spike_events,
            {name: pop.size for name, pop in self.network.populations.items()},
            self.simulation_config.t_sim,
        )


    def get_spike_events(self, population: str) -> dict:
        """
        Return spike events for one population as {"senders": ..., "times": ...}.
        """

        senders, times = recording.load_spikes(self)
        node_ids = self.get_population(population)
        return spikes.spikes_in_id_range(senders, times, int(node_ids[0]), int(node_ids[-1]))
    def save_recordings(self, run_dir: Path) -> list[Path]:
        """
        Write the spikes as ``recordings/spikes.csv`` and each recorded variable
        as ``recordings/<variable>.csv`` (columns ``sender``, ``time_ms`` and the
        variable's name, as NEST's files), and return the files.

        A variable is saved in the unit of the config files: mV, ms, pA, nS, Hz
        (spikes/s) or without a unit. Any other dimension is saved in Brian2's
        base unit (SI).
        """

        return recording.save_recordings(self, run_dir)


# The class get_backend() returns (see backends/__init__.py).
Backend = Brian2Backend
