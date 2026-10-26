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
from microcircuit_lab.config.connection_table import COLUMNS
from microcircuit_lab.config.connectivity import SHARED_DISTRIBUTIONS, SHARED_RULES
from microcircuit_lab.config.distributions import DrawnValue
from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.config.simulation import SimulationConfig
from microcircuit_lab.config.stimuli import (
    DcStimulusConfig,
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

        self._network = network
        self._simulation_config = simulation_config
        self._device = device
        self._codegen_target = codegen_target
        self._standalone_directory = standalone_directory
        self._extensions = extensions
        self._rng = np.random.default_rng(simulation_config.rng_seed)
        self._standalone_dir: tempfile.TemporaryDirectory | None = None
        self._neuron_models: dict[str, models.NeuronModel] = {}
        self._synapse_models: dict[str, models.SynapseModel] = {}
        self._connection_rules: dict[str, models.ConnectionRule] = {}
        self._distributions: dict[str, models.Distribution] = {}
        self._checked = False
        self._groups: list[_Group] = []
        self._group_of: dict[str, _Group] = {}

        #: Each population as a Brian2 subgroup of its NeuronGroup.
        self.populations: dict[str, b2.Subgroup] = {}
        self.first_ids: dict[str, int] = {}
        self.stimulus_generators: list[b2.PoissonGroup] = []
        self.synapses: list[b2.Synapses] = []
        self.spike_recorders: list[tuple[_Group, b2.SpikeMonitor]] = []
        #: The monitors of each recorded variable: one per group.
        self.multimeters: dict[str, list[tuple[_Group, b2.StateMonitor]]] = {}
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
            directory = self._standalone_directory
            if directory is None:
                self._standalone_dir = tempfile.TemporaryDirectory(prefix="brian2_standalone_")
                directory = self._standalone_dir.name
            b2.set_device("cpp_standalone", directory=str(directory), build_on_run=True)
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
        one that is not defined, if a distribution's ``redraw_rounds`` is
        needed but not set, if a project rule with several synapses per
        pair is used without multapses, or if a weight's ``unit`` is not that
        of the variable it adds to.
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

        # A weight's unit must be that of the variable it adds to (which also
        # checks that a port name is a variable of the target's model): once
        # per target, synapse, sign and unit.
        users = {}
        columns = (table["target"].tolist(), table["synapse"].tolist(),
                   (table["weight.mean"] >= 0).tolist(), table["weight.unit"].tolist())
        for row, (target, synapse, positive, unit) in enumerate(zip(*columns)):
            users.setdefault((target, synapse, positive, unit), f"connections.{row} ({table['source'][row]} -> {target})")
        for name, background in self._network.poisson_background.items():
            key = (name, background.synapse, background.weight.mean >= 0, background.weight.unit)
            users.setdefault(key, f"background input of {name!r}")
        for stimulus in self._network.stimuli:
            if not isinstance(stimulus, DcStimulusConfig):
                for target in stimulus.targets:
                    key = (target, stimulus.synapse, stimulus.weight.mean >= 0, stimulus.weight.unit)
                    users.setdefault(key, f"stimulus onto {target!r}")
        for (target, synapse, positive, unit), user in users.items():
            variable = self._target_variable(target, synapse, 1.0 if positive else -1.0)
            expected = self._weight_units(target, variable)[1]
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

        if self._simulation_config.recording.spike_recording:
            self.create_spike_recorders()

        if self._simulation_config.recording.variables:
            self.create_multimeters()

        self.create_poisson_background()

        if self._network.stimuli:
            self.create_stimuli()

        self.create_connections()

    def neuron_model(self, population: str) -> models.NeuronModel:
        """The Brian2 model of a population."""

        name = self._network.populations[population].neuron.model
        if name not in self._neuron_models:
            raise models.missing_model_error("neuron", name, self._neuron_models)
        return self._neuron_models[name]

    def _equations_text(self, population: str) -> str:
        """The equations of a population's model, for its parameters if they
        depend on them."""

        model = self.neuron_model(population)
        if callable(model.equations):
            return model.equations(dict(self._network.populations[population].neuron.parameters))
        return model.equations

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
        has the variables of that input (see create_poisson_background).
        """

        by_equations: dict[tuple[str, str], _Group] = {}
        values: dict[str, dict] = {}
        for pop_name, pop_cfg in self._network.populations.items():
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
            self._group_of[pop_name] = group
        self._groups = list(by_equations.values())

        first_id = 1
        for pop_name, pop_cfg in self._network.populations.items():
            self.first_ids[pop_name] = first_id
            first_id += pop_cfg.size

        dc_curves, dc_index = inputs.dc_curves(self)
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
            equations += inputs.background_equations(self, group)

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

        variable = model.excitatory if weight_mean >= 0 else model.inhibitory
        if variable is None:
            raise ValueError(
                f"The Brian2 model {model.name!r} of {target!r} needs a receptor_port in "
                "synapses.yaml for each connection to it."
            )
        return variable

    def _weight_units(self, target: str, variable: str) -> tuple[str, str]:
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
            *(group.neurons for group in self._groups),
            *self.stimulus_generators,
            *self.synapses,
            *(monitor for _, monitor in self.spike_recorders),
            *(monitor for monitors in self.multimeters.values() for _, monitor in monitors),
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

        log_firing_rates(
            logger,
            self.get_spike_events,
            {name: pop.size for name, pop in self._network.populations.items()},
            self._simulation_config.t_sim,
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
