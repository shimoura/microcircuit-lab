"""
Brian2 backend: creates and connects the network and runs the simulation.

The neuron and synapse models come from the project (``models.py``). Weights,
delays and per-neuron values are drawn in ``distributions.py``, and the pairs
of neurons that connect are picked in ``connections.py``. Brian2 keeps the
spikes in memory; they are saved as ``spikes.csv``, which ``spike_files.py``
reads without Brian2.

Brian2 spends time on every object it has, at every step and when it
generates code, so the network is made of as few objects as it can be: the
populations of one neuron model are one ``NeuronGroup`` (each a range of its
neurons), and all connections between two groups through the same synapse
are one ``Synapses``. Every object and table gets a name fixed by the
network: Brian2 puts the names in the code it generates, so a network built
again (in a sweep, or in the next run) reuses the code compiled before. Neurons are numbered as in NEST: population after
population, from 1.
"""

from __future__ import annotations

import functools
import logging
import tempfile
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import brian2 as b2
import numpy as np
from brian2.units.fundamentalunits import DIMENSIONLESS

from microcircuit_lab.backends import population_spikes
from microcircuit_lab.backends.brian2 import connections, distributions, models
from microcircuit_lab.config.connection_table import COLUMNS
from microcircuit_lab.config.connectivity import SHARED_DISTRIBUTIONS, SHARED_RULES
from microcircuit_lab.config.distributions import DrawnValue
from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.config.simulation import SimulationConfig
from microcircuit_lab.config.stimuli import (
    DcStimulusConfig,
    InhomogeneousPoissonStimulusConfig,
    PoissonStimulusConfig,
)

logger = logging.getLogger(__name__)

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
def _variable_names(equations: str) -> set[str]:
    """The variables of a model's equations (parsed once per text: a port name
    is looked up for every connection onto the model)."""
    return b2.Equations(equations).names


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
        extensions: Sequence[str] = (),
    ) -> None:
        """
        Parameters
        ----------
        network, simulation_config
            The prepared network and the simulation settings.
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
        extensions
            Python modules that define neuron and synapse models, besides the
            files in ``extensions/brian2/`` of the folder you run from.
        """

        if device not in ("runtime", "cpp_standalone"):
            raise ValueError(f"Unknown Brian2 device {device!r}; use 'runtime' or 'cpp_standalone'.")
        if codegen_target not in ("auto", "cython", "numpy"):
            raise ValueError(
                f"Unknown Brian2 codegen_target {codegen_target!r}; use 'auto', 'cython' or 'numpy'."
            )

        self._network = network
        self._simulation_config = simulation_config
        self._device = device
        self._codegen_target = codegen_target
        self._extensions = extensions
        self._rng = np.random.default_rng(simulation_config.rng_seed)
        self._standalone_dir: tempfile.TemporaryDirectory | None = None
        self._neuron_models: dict[str, models.NeuronModel] = {}
        self._synapse_models: dict[str, models.SynapseModel] = {}
        self._connection_rules: dict[str, models.ConnectionRule] = {}
        self._distributions: dict[str, models.Distribution] = {}
        self._groups: list[_Group] = []
        self._group_of: dict[str, _Group] = {}

        #: Each population as a Brian2 subgroup of its NeuronGroup.
        self.populations: dict[str, b2.Subgroup] = {}
        self.first_ids: dict[str, int] = {}
        self.stimulus_generators: list[b2.PoissonGroup] = []
        self.synapses: list[b2.Synapses] = []
        self.spike_recorders: list[tuple[_Group, b2.SpikeMonitor]] = []
        self.multimeters: list[tuple[_Group, b2.StateMonitor]] = []
        self._cached_spikes: tuple[np.ndarray, np.ndarray] | None = None

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

        if self._device == "cpp_standalone":
            self._standalone_dir = tempfile.TemporaryDirectory(prefix="brian2_standalone_")
            b2.set_device("cpp_standalone", directory=self._standalone_dir.name, build_on_run=True)
            b2.prefs.devices.cpp_standalone.openmp_threads = self._simulation_config.local_num_threads
        else:
            if self._simulation_config.local_num_threads > 1:
                logger.warning(
                    "Brian2's runtime device runs on one thread; local_num_threads=%d is used "
                    "only with the cpp_standalone device.",
                    self._simulation_config.local_num_threads,
                )
            b2.set_device("runtime")
            b2.prefs.codegen.target = self._codegen_target

        b2.defaultclock.dt = self._simulation_config.resolution * b2.ms
        b2.seed(self._simulation_config.rng_seed)
        self._rng = np.random.default_rng(self._simulation_config.rng_seed)

    def check(self) -> None:
        """
        Find the project's models, connection rules and distributions, and
        raise if a population, a ``synapses.yaml`` entry or a connection names
        one that is not defined, or if a distribution's ``redraw_rounds`` is
        needed but not set.
        """

        found = models.load_models(self._extensions)
        self._neuron_models = found[models.NeuronModel]
        self._synapse_models = found[models.SynapseModel]
        self._connection_rules = found[models.ConnectionRule]
        self._distributions = found[models.Distribution]
        for population in self._network.populations:
            self.neuron_model(population)
        for synapse in self._network.synapses:
            self.synapse_model(synapse)

        table = self._network.connections
        for column, kind, known in (
            ("rule", "rule", self._connection_rules),
            ("weight.distribution", "distribution", self._distributions),
            ("delay.distribution", "distribution", self._distributions),
        ):
            shared = SHARED_RULES if kind == "rule" else SHARED_DISTRIBUTIONS
            for name in sorted(set(table[column][~np.isin(table[column], shared)].tolist())):
                if name not in known:
                    raise models.missing_model_error(kind, name, known)
                if kind == "distribution" and self._network.bound_mode == "redraw" and known[name].redraw_rounds is None:
                    raise ValueError(
                        f"Distribution {name!r} has no redraw_rounds, which bound_mode: redraw needs: "
                        "set how many times a value past its bound is drawn again (0: clip at once), "
                        "or set bound_mode: clip in connectivity.yaml."
                    )

        # A port name must be a variable of each target's model: once per pair.
        named = {name for name in self._network.synapses if isinstance(self._network.receptor_port(name), str)}
        if named:
            for target, synapse in set(zip(table["target"].tolist(), table["synapse"].tolist())):
                if synapse in named:
                    self._target_variable(target, synapse, 0.0)

    def build(self) -> None:
        """
        Build the complete network. It calls :meth:`check` first, so a
        backend used without ``Simulation`` also fails before building.
        """

        self.check()
        self.initialize()

        self.create_populations()

        if self._simulation_config.recording.spike_recording:
            self.create_spike_recorders()

        if self._simulation_config.recording.voltage_recording:
            self.create_multimeters()

        self.create_background_inputs()

        if self._network.stimuli:
            self.create_stimuli()

        self.create_connections()

    def neuron_model(self, population: str) -> models.NeuronModel:
        """The Brian2 model of a population."""

        name = self._network.populations[population].neuron.model
        if name not in self._neuron_models:
            raise models.missing_model_error("neuron", name, self._neuron_models)
        return self._neuron_models[name]

    def synapse_model(self, synapse: str | None) -> models.SynapseModel:
        """The Brian2 model of a synapses.yaml entry (None: static_synapse)."""

        name = models.STATIC_SYNAPSE.name if synapse is None else self._network.synapses[synapse].model
        if name not in self._synapse_models:
            raise models.missing_model_error("synapse", name, self._synapse_models)
        return self._synapse_models[name]

    def create_populations(self) -> None:
        """
        Create all neuron populations: one NeuronGroup for the populations of
        each neuron model (and of each set of equations, for a model whose
        equations depend on its parameters).

        Every neuron knows its ``population_index`` in its group, and its
        ``index`` within its population (for connection rules). A group with
        ``dc`` stimuli reads its current from one table of all their currents,
        at each neuron's ``dc_index``. A group with Poisson background input
        has the variables of that input (see create_background_inputs).
        """

        by_equations: dict[tuple[str, str], _Group] = {}
        values: dict[str, dict] = {}
        for pop_name, pop_cfg in self._network.populations.items():
            model = self.neuron_model(pop_name)
            parameters = dict(pop_cfg.neuron.parameters)
            text = model.equations(parameters) if callable(model.equations) else model.equations
            equations = b2.Equations(text)

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
                    + (" I_e is also set by a compensation current (scaling, background_mode: "
                       "mean_current)." if "I_e" in unknown else "")
                )

            group = by_equations.setdefault((model.name, str(equations)), _Group(model, equations))
            group.populations.append(pop_name)
            group.starts.append(group.size)
            group.size += pop_cfg.size
            self._group_of[pop_name] = group
        self._groups = list(by_equations.values())

        first_id = 1
        for pop_name, pop_cfg in self._network.populations.items():
            self.first_ids[pop_name] = first_id
            first_id += pop_cfg.size

        dc_curves, dc_index = self._dc_curves()
        for group in self._groups:
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
            equations += self._background_equations(group)

            neurons = b2.NeuronGroup(
                group.size,
                equations,
                threshold=group.model.threshold,
                reset=group.model.reset,
                refractory=group.model.refractory,
                method=group.model.method,
                namespace=namespace,
                name=f"group_{self._groups.index(group)}",
            )
            group.neurons = neurons
            self._set_group_values(group, values)
            sizes = [self._network.populations[pop].size for pop in group.populations]
            neurons.population_index = np.repeat(np.arange(len(group.populations)), sizes)
            neurons.index = np.concatenate([np.arange(size) for size in sizes])
            if has_dc:
                neurons.dc_index = np.repeat(
                    [dc_index[pop] for pop in group.populations],
                    [self._network.populations[pop].size for pop in group.populations],
                )
            for pop_name, start in zip(group.populations, group.starts):
                self.populations[pop_name] = neurons[start:start + self._network.populations[pop_name].size]

    def _set_group_values(self, group: _Group, values: dict[str, dict]) -> None:
        """Set the parameters and initial state of a group's neurons, given in
        the package's units: one array per variable, for all its populations."""

        for name in sorted({name for pop in group.populations for name in values[pop]}):
            unit = _units(group.neurons.variables[name].dim, f"{name!r} of {group.model.name!r}")[1]
            array = np.zeros(group.size)
            for pop_name, start in zip(group.populations, group.starts):
                if name in values[pop_name]:
                    size = self._network.populations[pop_name].size
                    array[start:start + size] = distributions.per_neuron_value(
                        values[pop_name][name], size, self._rng
                    )
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
            if isinstance(value, DrawnValue):
                raise ValueError(f"{where}: {name!r} must be a number in the Brian2 backend.")
            setattr(target, name, value * getattr(b2, unit, 1))

    def _target_variable(self, target: str, synapse: str | None, weight_mean: float) -> str:
        """
        The variable of the target population that a connection adds to: the
        one of its synapse's receptor port (a port name is the variable), or
        else the model's excitatory or inhibitory one, as the weight's sign
        says (as in NEST).
        """

        model = self.neuron_model(target)
        port = self._network.receptor_port(synapse)
        if isinstance(port, str):
            parameters = dict(self._network.populations[target].neuron.parameters)
            text = model.equations(parameters) if callable(model.equations) else model.equations
            names = _variable_names(text)
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

        variable = model.excitatory if weight_mean >= 0 else model.inhibitory
        if variable is None:
            raise ValueError(
                f"The Brian2 model {model.name!r} of {target!r} needs a receptor_port in "
                "synapses.yaml for each connection to it."
            )
        return variable

    def _weight_units(self, target: str, variable: str) -> tuple[str, str]:
        """The units of the weights onto ``variable`` of ``target``: its name in
        equations and NEST's unit (pA for a current, nS for a conductance)."""

        equations = self._group_of[target].equations
        if variable not in equations.names:
            raise ValueError(
                f"The Brian2 model {self.neuron_model(target).name!r} of {target!r} has no "
                f"variable {variable!r} for its connections to add to."
            )
        return _units(equations[variable].dim, f"{variable!r} of {target!r}")

    def _make_synapses(
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
    ) -> None:
        """
        One Brian2 ``Synapses`` from ``source`` to the group ``target``, onto
        ``variable``, through the model of ``synapse``: made by the
        ``connect`` calls ``calls`` (see connections.connect_calls), named
        ``name``, with the
        weights and delays of each entry by ``index`` (see
        distributions.set_drawn), from a project distribution for the entries
        in ``projects["weight"]`` / ``projects["delay"]``. A weight onto a
        conductance is its size, as in NEST.
        """

        projects = projects or {"weight": {}, "delay": {}}

        si_unit, unit = self._weight_units(target.populations[0], variable)
        model = self.synapse_model(synapse)

        def code(on):
            if isinstance(on, dict):
                return {k: v.format(target=f"{variable}_post") for k, v in on.items()}
            return on.format(target=f"{variable}_post")

        pathways = {
            *(model.on_pre if isinstance(model.on_pre, dict) else ["pre"] * bool(model.on_pre)),
            *(model.on_post if isinstance(model.on_post, dict) else ["post"] * bool(model.on_post)),
        }
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
            on_pre=code(model.on_pre),
            on_post=code(model.on_post) or None,
            namespace={},
            name=name,
            **options,
        )
        for arguments, namespace in calls:
            synapses.namespace.update(namespace)
            synapses.connect(**arguments)

        if si_unit == "siemens":
            weights = {k: (abs(mean), *rest) for k, (mean, *rest) in weights.items()}
        bound_mode = self._network.bound_mode
        distributions.set_weights(synapses, "w_syn", index, weights, unit, bound_mode, projects["weight"])
        if "pre" in pathways:  # a gap junction has no pathway of spikes to delay
            distributions.set_delays(
                synapses, index, delays, bound_mode, self._simulation_config.resolution, projects["delay"]
            )

        parameters = {} if synapse is None else self._network.synapses[synapse].parameters
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

        table = self._network.connections
        column = {name: table[name].tolist() for name in COLUMNS}
        objects: dict[tuple, list[int]] = defaultdict(list)
        seen: dict[tuple, int] = defaultdict(int)
        for row in range(len(table)):
            source, target, synapse = column["source"][row], column["target"][row], column["synapse"][row]
            variable = self._target_variable(target, synapse, column["weight.mean"][row])
            key = (id(self._group_of[source]), id(self._group_of[target]), synapse, variable)
            pair = (*key, source, target)
            objects[(*key, seen[pair])].append(row)
            seen[pair] += 1

        for (_, _, synapse, variable, _), rows in objects.items():
            source = self._group_of[column["source"][rows[0]]]
            target = self._group_of[column["target"][rows[0]]]
            placed = [
                connections.Row(
                    rule=column["rule"][row],
                    number=column["number"][row],
                    source_start=source.start(column["source"][row]),
                    source_size=self._network.populations[column["source"][row]].size,
                    target_start=target.start(column["target"][row]),
                    target_size=self._network.populations[column["target"][row]].size,
                    autapses=True if column["allow_autapses"][row] is None else bool(column["allow_autapses"][row]),
                    multapses=True if column["allow_multapses"][row] is None else bool(column["allow_multapses"][row]),
                    same_population=column["source"][row] == column["target"][row],
                    parameters=column["parameters"][row] or {},
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
                for what in projects:
                    distribution = self._distributions.get(column[f"{what}.distribution"][row])
                    if distribution is not None:
                        projects[what][pair] = (distribution, column[f"{what}.parameters"][row] or {})
                weights[pair] = (
                    column["weight.mean"][row], column["weight.rel_std"][row],
                    column["weight.distribution"][row], number,
                )
                delays[pair] = (
                    column["delay.mean"][row], column["delay.rel_std"][row],
                    column["delay.distribution"][row], column["delay.minimum"][row], number,
                )
            self._make_synapses(
                source.neurons, target, synapse, variable, calls, name,
                f"population_index_pre*{n_target} + population_index_post", weights, delays, projects,
            )

    def get_population(self, name: str) -> np.ndarray:
        """
        The node IDs of a population.
        """

        first_id = self.first_ids[name]
        return np.arange(first_id, first_id + self._network.populations[name].size)

    def create_spike_recorders(self) -> None:
        """
        Create one spike monitor per group.
        """

        for group in self._groups:
            self.spike_recorders.append((group, b2.SpikeMonitor(group.neurons, name=f"{group.neurons.name}_spikes")))

    def create_multimeters(self) -> None:
        """
        Create one monitor of the membrane potential per group, of the first
        ``voltage_sample_size`` neurons of each population (all, if not set).
        """

        recording = self._simulation_config.recording
        for group in self._groups:
            record = np.concatenate([
                start + np.arange(min(recording.voltage_sample_size or size, size))
                for start, size in zip(group.starts, (self._network.populations[p].size for p in group.populations))
            ])
            self.multimeters.append(
                (group, b2.StateMonitor(
                    group.neurons, "V_m", record=record, dt=recording.voltage_interval * b2.ms,
                    name=f"{group.neurons.name}_voltage",
                ))
            )

    def _node_ids(self, group: _Group, indices: np.ndarray) -> np.ndarray:
        """The NEST-style node IDs of neurons of a group, from their indices in it."""

        starts = np.asarray(group.starts)
        population = np.searchsorted(starts, indices, side="right") - 1
        first_ids = np.asarray([self.first_ids[pop] for pop in group.populations])
        return first_ids[population] + indices - starts[population]

    def _poisson_background(self, pop_name: str):
        """The background input of a population if it is Poisson input, else None."""

        if self._network.background_mode == "mean_current":
            return None
        return self._network.background_inputs.get(pop_name)

    def _background_variables(self, group: _Group) -> dict[str, list[str]]:
        """The variables the group's Poisson background inputs add to, each
        with its populations."""

        variables: dict[str, list[str]] = defaultdict(list)
        for pop_name in group.populations:
            background = self._poisson_background(pop_name)
            if background is not None:
                variable = self._target_variable(pop_name, background.synapse, background.weight.mean)
                variables[variable].append(pop_name)
        return variables

    def _background_equations(self, group: _Group) -> b2.Equations:
        """The variables of the group's Poisson background input: the weight
        ``w_background`` of each neuron's input and, for each variable it adds
        to, its mean number of spikes per step ``background_<variable>``."""

        variables = self._background_variables(group)
        if not variables:
            return b2.Equations("")
        units = {self._weight_units(pops[0], variable)[0] for variable, pops in variables.items()}
        if len(units) > 1:
            raise ValueError(
                f"The background inputs of {group.populations} add to variables of different units."
            )
        lines = [f"w_background : {units.pop()} (constant)"]
        lines += [f"background_{variable} : 1 (constant)" for variable in variables]
        return b2.Equations("\n".join(lines))

    def create_background_inputs(self) -> None:
        """
        Give each configured population its background Poisson input.

        Does nothing when background_mode is "mean_current": prepare_network has
        already added the background input to each neuron's I_e as a constant
        current (see NetworkConfig.background_mode).

        As from NEST's poisson_generator, each neuron gets its own Poisson
        number of spikes at each step, at the prepared rate (rate x indegree),
        also for populations that share a ``generator``, each with the weight
        drawn for that neuron. One update per group and variable does this
        for all of them. The input's delay is left out: it only shifts a
        stationary Poisson train in time.
        """

        if self._network.background_mode == "mean_current":
            logger.info(
                "background_mode='mean_current': background drive is constant current "
                "(I_e), skipping Poisson generators."
            )
            return

        for group in self._groups:
            variables = self._background_variables(group)
            if not variables:
                continue
            weights = {}
            for variable, pops in variables.items():
                rates = np.zeros(group.size)
                for pop_name in pops:
                    background = self._network.background_inputs[pop_name]
                    if self.synapse_model(background.synapse) is not self._synapse_models["static_synapse"]:
                        raise NotImplementedError(
                            f"The background input of {pop_name!r} uses synapse {background.synapse!r}; "
                            "the Brian2 backend connects background input only through static synapses."
                        )
                    start, size = group.start(pop_name), self._network.populations[pop_name].size
                    rates[start:start + size] = background.rate * self._simulation_config.resolution / 1000.0
                    weight = background.weight
                    mean = abs(weight.mean) if self._weight_units(pop_name, variable)[0] == "siemens" else weight.mean
                    weights[group.populations.index(pop_name)] = (mean, weight.rel_std, weight.distribution, size)
                setattr(group.neurons, f"background_{variable}", rates)
                group.neurons.run_regularly(
                    f"{variable} += w_background*poisson(background_{variable})", when="synapses",
                    name=f"{group.neurons.name}_background_{variable}",
                )
            unit = self._weight_units(next(iter(variables.values()))[0], next(iter(variables)))[1]
            distributions.set_weights(
                group.neurons, "w_background", "population_index", weights, unit, self._network.bound_mode
            )

    def _stimulus_curve(self, stimulus) -> np.ndarray:
        """
        The amplitude (pA) of a dc stimulus, or the rate (Hz) of a Poisson one,
        at every time step of the simulation, 0 outside [start, stop).
        An inhomogeneous rate holds each value until the next time, as in NEST.
        """

        dt = self._simulation_config.resolution
        t = np.arange(int(np.ceil(self._simulation_config.t_sim / dt)) + 1) * dt

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

    def _dc_curves(self) -> tuple[b2.TimedArray, dict[str, int]]:
        """
        The current of the dc stimuli of each population, as one table (time
        step x curve) and each population's curve in it (0: no current).
        """

        curves = [np.zeros(int(np.ceil(self._simulation_config.t_sim / self._simulation_config.resolution)) + 1)]
        index = {}
        for pop_name in self._network.populations:
            dc = [
                self._stimulus_curve(stimulus)
                for stimulus in self._network.stimuli
                if isinstance(stimulus, DcStimulusConfig) and pop_name in stimulus.targets
            ]
            index[pop_name] = 0
            if dc:
                index[pop_name] = len(curves)
                curves.append(np.sum(dc, axis=0))
        table = b2.TimedArray(
            np.column_stack(curves) * b2.pA, dt=self._simulation_config.resolution * b2.ms, name="dc_current"
        )
        return table, index

    def create_stimuli(self) -> None:
        """
        Create and connect the Poisson stimuli: for each target, one Poisson
        spike train per neuron, connected with the stimulus's weight, delay and
        synapse, as from NEST's generators. ``dc`` stimuli are part of their
        targets' equations (see create_populations).
        """

        logger.info("Creating stimulus devices:")
        resolution = self._simulation_config.resolution * b2.ms

        for stimulus in self._network.stimuli:
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
                self._stimulus_curve(stimulus) * b2.Hz, dt=resolution,
                name=f"stimulus_{self._network.stimuli.index(stimulus)}_rate",
            )

            for target in stimulus.targets:
                size = self._network.populations[target].size
                group = self._group_of[target]
                name = f"stimulus_{len(self.stimulus_generators)}"
                generator = b2.PoissonGroup(
                    size, rates="stimulus_rate(t)", namespace={"stimulus_rate": rate}, name=name
                )
                self.stimulus_generators.append(generator)
                weight, delay = stimulus.weight, stimulus.delay
                self._make_synapses(
                    generator,
                    group,
                    stimulus.synapse,
                    self._target_variable(target, stimulus.synapse, weight.mean),
                    [({"j": f"i + {group.start(target)}"}, {})],
                    f"{name}_synapses",
                    "0",
                    {0: (weight.mean, weight.rel_std, weight.distribution, size)},
                    {0: (delay.mean, delay.rel_std, delay.distribution, delay.minimum, size)},
                )

    def simulate(self) -> None:
        """
        Run the simulation, discarding any spike events cached from before it.
        """

        network = b2.Network(
            *(group.neurons for group in self._groups),
            *self.stimulus_generators,
            *self.synapses,
            *(monitor for _, monitor in self.spike_recorders),
            *(monitor for _, monitor in self.multimeters),
        )
        network.run(self._simulation_config.t_sim * b2.ms)
        self._cached_spikes = None

    def print_statistics(self) -> None:
        """
        Print simple statistics.
        """

        logger.info("")
        logger.info("Simulation statistics")
        logger.info("---------------------")

        if not self.spike_recorders:
            return

        population_spikes.log_firing_rates(
            logger,
            self.get_spike_events,
            {name: pop.size for name, pop in self._network.populations.items()},
            self._simulation_config.t_sim,
        )

    def _load_spikes(self) -> tuple[np.ndarray, np.ndarray]:
        """
        All spikes of the run as (senders, times), sorted by sender.
        Kept until the next simulate().
        """

        if self._cached_spikes is not None:
            return self._cached_spikes

        if not self.spike_recorders:
            self._cached_spikes = population_spikes.empty_spikes()
            return self._cached_spikes

        senders = [self._node_ids(group, np.asarray(monitor.i[:], dtype=int)) for group, monitor in self.spike_recorders]
        times = [np.asarray(monitor.t / b2.ms, dtype=float) for _, monitor in self.spike_recorders]
        self._cached_spikes = population_spikes.sort_by_sender(np.concatenate(senders), np.concatenate(times))
        return self._cached_spikes

    def get_spike_events(self, population: str) -> dict:
        """
        Return spike events for one population as {"senders": ..., "times": ...}.
        """

        senders, times = self._load_spikes()
        node_ids = self.get_population(population)
        return population_spikes.spikes_in_id_range(senders, times, int(node_ids[0]), int(node_ids[-1]))

    def save_recordings(self, run_dir: Path) -> list[Path]:
        """
        Write the spikes as ``recordings/spikes.csv`` and, if recorded, the
        membrane potentials as ``recordings/voltage.csv`` (columns ``sender``,
        ``time_ms`` and ``V_m``, as NEST's voltage files), and return the files.
        """

        recordings_dir = Path(run_dir) / "recordings"
        recordings_dir.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []

        if self.spike_recorders:
            path = recordings_dir / "spikes.csv"
            population_spikes.write_csv_spikes(path, *self._load_spikes())
            paths.append(path)

        if self.multimeters:
            tables = []
            for group, monitor in self.multimeters:
                times = np.asarray(monitor.t / b2.ms)
                senders = self._node_ids(group, np.asarray(monitor.record))
                voltages = np.asarray(monitor.V_m / b2.mV)
                tables.append(
                    np.column_stack(
                        [np.repeat(senders, len(times)), np.tile(times, len(senders)), voltages.ravel()]
                    )
                )
            path = recordings_dir / "voltage.csv"
            np.savetxt(
                path,
                np.concatenate(tables),
                delimiter=",",
                header="sender,time_ms,V_m",
                comments="",
                fmt=["%d", "%.3f", "%.3f"],
            )
            paths.append(path)

        return paths
