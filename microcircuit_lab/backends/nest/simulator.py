"""
NEST backend: creates and connects the network and runs the simulation.

Weights, delays and per-neuron values are built in ``distributions.py``;
NEST's spike files are read in ``spike_files.py``, which does not import NEST.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

import nest
import numpy as np

from microcircuit_lab.backends import population_spikes
from microcircuit_lab.backends.nest import distributions, spike_files
from microcircuit_lab.config.connection_table import COLUMNS
from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.config.populations import PopulationConfig
from microcircuit_lab.config.simulation import SimulationConfig
from microcircuit_lab.config.stimuli import (
    DcStimulusConfig,
    InhomogeneousPoissonStimulusConfig,
    PoissonStimulusConfig,
)

logger = logging.getLogger(__name__)


class NestBackend:
    """Builds the network in NEST, runs it and reads back the spikes."""

    def __init__(
        self,
        network: NetworkConfig,
        simulation_config: SimulationConfig,
        *,
        extension_modules: Sequence[str] = (),
    ) -> None:
        """
        Parameters
        ----------
        network, simulation_config
            The prepared network and the simulation settings.
        extension_modules
            Names of compiled NEST modules to install before the network is
            built, for example a NESTML neuron model that ``neurons.yaml`` uses.
            They are installed again at every build, because NEST is reset each
            time.
        """

        self._network = network
        self._simulation_config = simulation_config
        self._extension_modules = extension_modules
        self._recordings_dir: Path | None = None

        self.populations: dict[str, nest.NodeCollection] = {}
        self.background_generators: dict[str, nest.NodeCollection] = {}
        self.spike_recorder: nest.NodeCollection | None = None
        self.multimeter: nest.NodeCollection | None = None
        self.stimulus_generators: list[tuple] = []
        self._cached_spikes: tuple[np.ndarray, np.ndarray] | None = None

    def version(self) -> str:
        return nest.__version__

    def num_processes(self) -> int:
        return nest.NumProcesses()

    def rank(self) -> int:
        return nest.Rank()

    def sync_processes(self) -> None:
        nest.SyncProcesses()

    def prepare_output(self, run_dir: Path) -> None:
        """
        Point NEST's own ascii recording backend at ``run_dir/recordings``.

        NEST then writes the spikes to disk while it simulates, so the full
        spike history is never held in Python memory. Call it before build().
        Without it, the spike recorder keeps the spikes in memory (and
        get_spike_events and save_recordings still work).
        """

        self._recordings_dir = Path(run_dir) / "recordings"

    def initialize(self) -> None:
        """
        Initialize the NEST kernel.
        """

        nest.ResetKernel()

        for module in self._extension_modules:
            logger.info("Installing extension module %s", module)
            nest.Install(module)

        nest.set(
            resolution=self._simulation_config.resolution,
            local_num_threads=self._simulation_config.local_num_threads,
            rng_seed=self._simulation_config.rng_seed,
            print_time=self._simulation_config.print_time,
        )

        if self._recordings_dir is not None:
            self._recordings_dir.mkdir(parents=True, exist_ok=True)
            nest.set(
                data_path=str(self._recordings_dir),
                overwrite_files=True,
            )

    def build(self) -> None:
        """
        Build the complete network.
        """

        self.initialize()

        self.create_synapse_models()
        self.create_populations()

        if self._simulation_config.recording.spike_recording:
            self.create_spike_recorders()
            self.connect_spike_recorders()

        if self._simulation_config.recording.voltage_recording:
            self.create_multimeters()
            self.connect_multimeters()

        self.create_background_inputs()
        self.connect_background_inputs()

        if self._network.stimuli:
            self.create_stimuli()
            self.connect_stimuli()

        self.create_connections()

    def create_populations(self) -> None:
        """
        Create all neuron populations.
        """

        for pop_name, pop_cfg in self._network.populations.items():
            logger.info(
                "Creating %s (%d neurons)",
                pop_name,
                pop_cfg.size,
            )

            nodes = nest.Create(
                pop_cfg.neuron.model,
                pop_cfg.size,
            )

            self.initialize_population(nodes, pop_cfg)
            self.populations[pop_name] = nodes

    def initialize_population(
        self, nodes: nest.NodeCollection, pop_cfg: PopulationConfig
    ) -> None:
        """
        Initialize the parameters and state variables of a population.

        The neuron's parameters are set first, then the initial state; a
        value given as a distribution is drawn for every neuron.
        """

        for values in (dict(pop_cfg.neuron.parameters), pop_cfg.initial_state):
            nodes.set(
                {name: distributions.per_neuron_value(value) for name, value in values.items()}
            )

    def create_synapse_models(self) -> None:
        """
        Make each entry of synapses.yaml a NEST synapse model of that name,
        a copy of its ``model`` with its ``parameters``.
        """

        for name, entry in self._network.synapses.items():
            nest.CopyModel(entry.model, name, entry.parameters)

    def synapse_spec(self, weight, delay, synapse: str | None) -> dict:
        """
        The ``syn_spec`` of a connection: its weight and delay (made by
        distributions.py), and its synapse model and receptor port if it names
        a synapses.yaml entry.
        """

        spec = {"weight": weight, "delay": delay}
        if synapse is not None:
            spec["synapse_model"] = synapse
            receptor_port = self._network.receptor_port(synapse)
            if receptor_port is not None:
                spec["receptor_type"] = receptor_port
        return spec

    def weight_and_delay(self, weight, delay) -> tuple:
        """The NEST weight and delay of a background input or stimulus, from its
        ``weight`` and ``delay`` as written in the config files."""

        bound_mode = self._network.bound_mode
        return (
            distributions.create_weight_spec(weight.mean, weight.rel_std, weight.distribution, bound_mode),
            distributions.create_delay_parameter(
                delay.mean, delay.rel_std, delay.distribution, delay.minimum, bound_mode
            ),
        )

    def create_connections(self) -> None:
        """
        Connect populations according to the connectivity configuration:
        one ``nest.Connect`` per row of the connection table.
        """

        logger.info("Creating recurrent connections:")

        # NEST's name for the number each rule takes
        nest_number = {
            "fixed_total_number": "N",
            "fixed_indegree": "indegree",
            "fixed_outdegree": "outdegree",
            "pairwise_bernoulli": "p",
        }

        table = self._network.connections
        bound_mode = self._network.bound_mode
        resolution = nest.resolution
        rows_per_piece = 100_000

        for start in range(0, len(table), rows_per_piece):
            stop = min(start + rows_per_piece, len(table))
            # The rows of this piece, each column as a plain list: reading a
            # numpy array value by value is slow, and lists of whole columns
            # would take gigabytes for millions of connections.
            column = {name: table[name][start:stop].tolist() for name in COLUMNS}

            for i in range(stop - start):
                source, target, rule = column["source"][i], column["target"][i], column["rule"][i]
                number = column["number"][i]
                if rule != "pairwise_bernoulli":
                    number = int(number)
                synapse = column["synapse"][i]
                weight = distributions.create_weight_spec(
                    column["weight.mean"][i],
                    column["weight.rel_std"][i],
                    column["weight.distribution"][i],
                    bound_mode,
                )
                delay = distributions.create_delay_parameter(
                    column["delay.mean"][i],
                    column["delay.rel_std"][i],
                    column["delay.distribution"][i],
                    column["delay.minimum"][i],
                    bound_mode,
                    resolution,
                )

                logger.debug(
                    "Connecting %s -> %s (%s=%g, synapse=%s, weight=%g, delay=%g)",
                    source, target, nest_number[rule], number, synapse or "default",
                    column["weight.mean"][i], column["delay.mean"][i],
                )

                conn_spec = {"rule": rule, nest_number[rule]: number}
                for option in ("allow_autapses", "allow_multapses"):
                    if column[option][i] is not None:
                        conn_spec[option] = bool(column[option][i])

                nest.Connect(
                    self.populations[source],
                    self.populations[target],
                    conn_spec=conn_spec,
                    syn_spec=self.synapse_spec(weight, delay, synapse),
                )

    def get_population(
        self,
        name: str,
    ) -> nest.NodeCollection:
        """
        Get the NEST node collection corresponding to a population name.
        """

        return self.populations[name]

    def create_spike_recorders(self) -> None:
        """
        Create one shared spike recorder for all populations.

        Records straight to ascii files under the directory set in
        prepare_output(), if any; otherwise keeps events in memory (NEST's
        default), matching the standalone-backend / no-output-requested case.
        """

        params = (
            {"record_to": "ascii", "label": "spikes"}
            if self._recordings_dir is not None
            else {}
        )
        self.spike_recorder = nest.Create("spike_recorder", params=params)

    def connect_spike_recorders(self) -> None:
        """
        Connect populations to the shared spike recorder.
        """

        for pop_name in self.populations:
            nest.Connect(
                self.get_population(pop_name),
                self.spike_recorder,
            )

    def create_multimeters(self) -> None:
        """
        Create one shared multimeter recording membrane potential.

        Records straight to ascii files under the directory set in
        prepare_output(), if any, same as spike recorders; otherwise
        keeps events in NEST's default in-memory mode.
        """

        params = {
            "record_from": ["V_m"],
            "interval": self._simulation_config.recording.voltage_interval,
        }
        if self._recordings_dir is not None:
            params.update({"record_to": "ascii", "label": "voltage"})

        self.multimeter = nest.Create("multimeter", params=params)

    def connect_multimeters(self) -> None:
        """
        Connect the shared multimeter to populations (with optional subsampling).
        """

        sample_size = self._simulation_config.recording.voltage_sample_size

        for pop_name in self.populations:
            nodes = self.get_population(pop_name)
            if sample_size is not None and sample_size < len(nodes):
                nodes = nodes[:sample_size]
            nest.Connect(
                self.multimeter,
                nodes,
            )

    def create_background_inputs(self) -> None:
        """
        Create one background Poisson generator per configured population.

        Does nothing when background_mode is "mean_current": prepare_network has
        already added the background input to each neuron's I_e as a constant
        current (see NetworkConfig.background_mode).
        """

        if self._network.background_mode == "mean_current":
            logger.info(
                "background_mode='mean_current': background drive is constant current "
                "(I_e), skipping Poisson generators."
            )
            return

        logger.info("Creating background Poisson generators:")

        for pop_name, input_cfg in self._network.background_inputs.items():
            logger.info(
                "Creating background Poisson input for %s (rate=%g Hz)",
                pop_name,
                input_cfg.rate,
            )
            pg = nest.Create(
                "poisson_generator",
                params={
                    "rate": input_cfg.rate,
                },
            )
            self.background_generators[pop_name] = pg

    def connect_background_inputs(self) -> None:
        """
        Connect background Poisson generators to populations.
        """

        for pop_name in self.background_generators:
            input_cfg = self._network.background_inputs[pop_name]
            weight, delay = self.weight_and_delay(input_cfg.weight, input_cfg.delay)
            nest.Connect(
                self.background_generators[pop_name],
                self.get_population(pop_name),
                syn_spec=self.synapse_spec(weight, delay, input_cfg.synapse),
            )

    def create_stimuli(self) -> None:
        """
        Create one device per configured stimulus, according to its type
        (dc, poisson or inhomogeneous_poisson).
        """

        logger.info("Creating stimulus devices:")

        for stimulus in self._network.stimuli:
            logger.info(
                "Creating %s stimulus for %s (start=%g, stop=%s)",
                stimulus.type,
                stimulus.targets,
                stimulus.start,
                stimulus.stop,
            )

            params: dict = {"start": stimulus.start}
            if stimulus.stop is not None:
                params["stop"] = stimulus.stop

            if isinstance(stimulus, DcStimulusConfig):
                model = "dc_generator"
                params["amplitude"] = stimulus.amplitude
            elif isinstance(stimulus, PoissonStimulusConfig):
                model = "poisson_generator"
                params["rate"] = stimulus.rate
            elif isinstance(stimulus, InhomogeneousPoissonStimulusConfig):
                model = "inhomogeneous_poisson_generator"
                params["rate_times"] = stimulus.rate_times
                params["rate_values"] = stimulus.rate_values
            else:
                raise ValueError(f"Unsupported stimulus type: {type(stimulus).__name__!r}")

            device = nest.Create(model, params=params)
            self.stimulus_generators.append((stimulus, device))

    def connect_stimuli(self) -> None:
        """
        Connect each stimulus device to its target populations.

        `dc` devices are connected with the default synapse (weight 1.0
        per pA of amplitude); `poisson`/`inhomogeneous_poisson` devices
        use the configured weight, delay and synapse, same as background input.
        """

        for stimulus, device in self.stimulus_generators:
            syn_spec = None
            if not isinstance(stimulus, DcStimulusConfig):
                weight, delay = self.weight_and_delay(stimulus.weight, stimulus.delay)
                syn_spec = self.synapse_spec(weight, delay, stimulus.synapse)

            for target in stimulus.targets:
                nest.Connect(device, self.get_population(target), syn_spec=syn_spec)

    def simulate(self) -> None:
        """
        Run the simulation, discarding any spike events cached from before it.
        """

        nest.Simulate(self._simulation_config.t_sim)
        self._cached_spikes = None

    def print_statistics(self) -> None:
        """
        Print simple statistics.
        """

        logger.info("")
        logger.info("Simulation statistics")
        logger.info("---------------------")

        if self.spike_recorder is None:
            return

        t_sim_s = self._simulation_config.t_sim / 1000.0

        for pop_name in self.populations:
            events = self.get_spike_events(pop_name)
            n_spikes = len(events["times"])
            n_neurons = self._network.populations[pop_name].size
            mean_rate = (n_spikes / (n_neurons * t_sim_s)) if (n_neurons and t_sim_s > 0) else 0.0

            logger.info(
                "%-6s  N=%5d  spikes=%7d  rate=%8.3f Hz",
                pop_name,
                n_neurons,
                n_spikes,
                mean_rate,
            )

    def _load_spikes(self) -> tuple[np.ndarray, np.ndarray]:
        """
        All spikes of the run as (senders, times), sorted by sender: read from
        the ascii files NEST wrote, or taken from the recorder's memory.
        Kept until the next simulate().
        """

        if self._cached_spikes is not None:
            return self._cached_spikes

        if self.spike_recorder is None:
            self._cached_spikes = population_spikes.empty_spikes()
        elif self.spike_recorder.get("record_to") == "ascii":
            paths = spike_files.ascii_spike_files(self._recordings_dir)
            self._cached_spikes = spike_files.read_ascii_spikes(paths)
        else:
            self._cached_spikes = self._memory_spikes()

        return self._cached_spikes

    def _memory_spikes(self) -> tuple[np.ndarray, np.ndarray]:
        """The spikes the recorder kept in memory, sorted by sender."""

        events = self.spike_recorder.get("events")
        senders = np.asarray(events["senders"], dtype=int)
        times = np.asarray(events["times"], dtype=float)
        return population_spikes.sort_by_sender(senders, times)

    def get_spike_events(
        self,
        population: str,
    ) -> dict:
        """
        Return spike events for one population as {"senders": ..., "times": ...}.

        Takes the spikes of the node IDs of this population from the shared
        spike events.
        """

        senders, times = self._load_spikes()
        node_ids = self.get_population(population).tolist()
        return population_spikes.spikes_in_id_range(senders, times, int(node_ids[0]), int(node_ids[-1]))

    def save_recordings(self, run_dir: Path) -> list[Path]:
        """
        Return the spike (and, if enabled, voltage) recording files for
        this run.

        In ascii mode NEST has already written the files during simulate().
        Without prepare_output(), the spikes are in memory and are written here
        as a CSV file. Voltage is not: voltage traces are large, so voltage
        recorded in memory is not saved.
        """

        run_dir = Path(run_dir)
        paths: list[Path] = []

        if self.spike_recorder is not None:
            if self.spike_recorder.get("record_to") == "ascii":
                paths.extend(sorted(self._recordings_dir.glob("spikes-*.dat")))
            else:
                paths.append(self._write_memory_recording_csv(run_dir))

        if self.multimeter is not None:
            if self.multimeter.get("record_to") == "ascii":
                paths.extend(sorted(self._recordings_dir.glob("voltage-*.dat")))

        return paths

    def _write_memory_recording_csv(self, run_dir: Path) -> Path:
        recordings_dir = run_dir / "recordings"
        recordings_dir.mkdir(parents=True, exist_ok=True)
        path = recordings_dir / "spikes.csv"

        senders, times = self._memory_spikes()
        spike_files.write_csv_spikes(path, senders, times)
        return path
