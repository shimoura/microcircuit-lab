"""
NEST backend.

This module contains the first implementation of the simulator backend.
"""

from __future__ import annotations

import logging
from pathlib import Path

import nest
import numpy as np
import pandas as pd

from microcircuit_lab.network import Network
from microcircuit_lab.config.simulation import SimulationConfig
from microcircuit_lab.config.network import PopulationConfig

logger = logging.getLogger(__name__)


class NestBackend:
    """
    Simple NEST backend.
    """

    def __init__(
        self,
        network: Network,
        simulation_config: SimulationConfig,
    ) -> None:

        self._network = network
        self._simulation_config = simulation_config
        self._recordings_dir: Path | None = None

        self.populations: dict[str, nest.NodeCollection] = {}
        self.poisson_generators: dict[str, nest.NodeCollection] = {}
        self.spike_recorders: dict[str, nest.NodeCollection] = {}
        self.multimeters: dict[str, nest.NodeCollection] = {}
        self.stimulus_devices: list[tuple] = []

    def prepare_output(self, run_dir: Path) -> None:
        """
        Point NEST's own ascii recording backend at ``run_dir/recordings``.

        NEST then writes spikes straight to disk during simulate() -- it
        never has to hold the full spike history in Python memory, and we
        never re-serialize what NEST already wrote. Must be called before
        build(); without it, spike_recorders fall back to NEST's in-memory
        mode (used transparently by get_spike_events/save_recordings).
        """

        self._recordings_dir = Path(run_dir) / "recordings"

    def initialize(self) -> None:
        """
        Initialize the NEST kernel.
        """

        nest.ResetKernel()

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

        self.create_populations()

        if self._simulation_config.recording.spike_recording:
            self.create_spike_recorders()
            self.connect_spike_recorders()

        if self._simulation_config.recording.voltage_recording:
            self.create_multimeters()
            self.connect_multimeters()

        self.create_poisson_generators()

        self.connect_poisson_generators()

        if self._network.config.stimuli:
            self.create_stimulus_devices()
            self.connect_stimulus_devices()

        self.connect_recurrent_connections()

    def create_populations(self) -> None:
        """
        Create all neuron populations.
        """

        for pop_name, pop_cfg in self._network.config.populations.items():
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

        This includes neuron model parameters and the initial membrane
        potential distribution.
        """

        nodes.set(pop_cfg.neuron.parameters.model_dump())

        nodes.V_m = nest.random.normal(
            mean=pop_cfg.V0_mean,
            std=pop_cfg.V0_std,
        )

    def connect_recurrent_connections(self) -> None:
        """
        Connect populations according to the connectivity configuration.
        """

        logger.info("Creating recurrent connections:")

        for connection in self._network.config.connections:
            source = self.get_population(connection.source)
            target = self.get_population(connection.target)

            logger.info(
                "Connecting %s -> %s (N=%d, weight=%g, delay=%g)",
                connection.source,
                connection.target,
                connection.n_synapses,
                connection.weight.mean,
                connection.delay.mean,
            )

            nest.Connect(
                source,
                target,
                conn_spec={
                    "rule": "fixed_total_number",
                    "N": connection.n_synapses,
                },
                syn_spec={
                    "weight": self.create_weight_spec(connection.weight),
                    "delay": self.create_delay_parameter(connection.delay),
                },
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
        Create one spike recorder per population.

        Records straight to ascii files under the directory set in
        prepare_output(), if any; otherwise keeps events in memory (NEST's
        default), matching the standalone-backend / no-output-requested case.
        """

        for pop_name in self.populations:
            params = (
                {"record_to": "ascii", "label": pop_name}
                if self._recordings_dir is not None
                else {}
            )
            sr = nest.Create("spike_recorder", params=params)

            self.spike_recorders[pop_name] = sr

    def connect_spike_recorders(self) -> None:
        """
        Connect populations to their spike recorders.
        """

        for pop_name in self.populations:
            nest.Connect(
                self.get_population(pop_name),
                self.spike_recorders[pop_name],
            )

    def create_multimeters(self) -> None:
        """
        Create one multimeter per population, recording membrane potential.

        Records straight to ascii files under the directory set in
        prepare_output(), if any, same as spike recorders; otherwise
        keeps events in NEST's default in-memory mode (not read back by
        save_recordings() -- ascii mode is the supported path).
        """

        for pop_name in self.populations:
            params = {
                "record_from": ["V_m"],
                "interval": self._simulation_config.recording.voltage_interval,
            }
            if self._recordings_dir is not None:
                params.update({"record_to": "ascii", "label": f"{pop_name}_voltage"})

            self.multimeters[pop_name] = nest.Create("multimeter", params=params)

    def connect_multimeters(self) -> None:
        """
        Connect multimeters to their populations.
        """

        for pop_name in self.populations:
            nest.Connect(
                self.multimeters[pop_name],
                self.get_population(pop_name),
            )

    def create_poisson_generators(self) -> None:
        """
        Create one background Poisson generator per configured population.
        """

        logger.info("Creating background Poisson generators:")

        for pop_name, input_cfg in self._network.config.background_inputs.items():
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
            self.poisson_generators[pop_name] = pg

    def connect_poisson_generators(self) -> None:
        """
        Connect background Poisson generators to populations.
        """

        for pop_name in self.poisson_generators:
            input_cfg = self._network.config.background_inputs[pop_name]
            nest.Connect(
                self.poisson_generators[pop_name],
                self.get_population(pop_name),
                syn_spec={
                    "weight": self.create_weight_spec(input_cfg.weight),
                    "delay": self.create_delay_parameter(input_cfg.delay),
                },
            )

    def create_stimulus_devices(self) -> None:
        """
        Create one device per configured stimulus, dispatching on
        `StimulusConfig.type` the same way create_weight_spec/
        create_delay_parameter dispatch on `distribution`.
        """

        logger.info("Creating stimulus devices:")

        for stimulus in self._network.config.stimuli:
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

            if stimulus.type == "dc":
                model = "dc_generator"
                params["amplitude"] = stimulus.amplitude
            elif stimulus.type == "poisson":
                model = "poisson_generator"
                params["rate"] = stimulus.rate
            elif stimulus.type == "inhomogeneous_poisson":
                model = "inhomogeneous_poisson_generator"
                params["rate_times"] = stimulus.rate_times
                params["rate_values"] = stimulus.rate_values
            else:
                raise ValueError(f"Unsupported stimulus type: {stimulus.type!r}")

            device = nest.Create(model, params=params)
            self.stimulus_devices.append((stimulus, device))

    def connect_stimulus_devices(self) -> None:
        """
        Connect each stimulus device to its target populations.

        `dc` devices are connected with the default synapse (weight 1.0
        per pA of amplitude); `poisson`/`inhomogeneous_poisson` devices
        use the configured weight/delay, same as background input.
        """

        for stimulus, device in self.stimulus_devices:
            syn_spec = None
            if stimulus.type != "dc":
                syn_spec = {
                    "weight": self.create_weight_spec(stimulus.weight),
                    "delay": self.create_delay_parameter(stimulus.delay),
                }

            for target in stimulus.targets:
                nest.Connect(device, self.get_population(target), syn_spec=syn_spec)

    def simulate(self) -> None:
        """
        Run the simulation.
        """

        nest.Simulate(self._simulation_config.t_sim)

    def print_statistics(self) -> None:
        """
        Print simple statistics.
        """

        logger.info("")
        logger.info("Simulation statistics")
        logger.info("---------------------")

        for pop_name in self.spike_recorders:
            sr = self.spike_recorders[pop_name]

            n_spikes = sr.n_events
            n_neurons = self._network.config.populations[pop_name].size
            t_sim_s = self._simulation_config.t_sim / 1000.0
            mean_rate = n_spikes / (n_neurons * t_sim_s)

            logger.info(
                "%-6s  N=%5d  spikes=%7d  rate=%8.3f Hz",
                pop_name,
                n_neurons,
                n_spikes,
                mean_rate,
            )

    def create_weight_spec(self, weight):
        """
        Create a NEST weight parameter.
        """

        if weight.distribution == "fixed":
            return weight.mean

        std = abs(weight.mean * weight.rel_std)

        if weight.distribution == "normal":
            if weight.mean >= 0:
                return nest.math.redraw(
                    nest.random.normal(
                        mean=weight.mean,
                        std=std,
                    ),
                    min=0.0,
                    max=float("inf"),
                )

            return nest.math.redraw(
                nest.random.normal(
                    mean=weight.mean,
                    std=std,
                ),
                min=-float("inf"),
                max=0.0,
            )

        if weight.distribution == "lognormal":
            variance = (weight.mean * weight.rel_std) ** 2
            sigma2 = np.log(1.0 + variance / weight.mean**2)
            sigma = np.sqrt(sigma2)
            mu = np.log(weight.mean) - sigma2 / 2.0

            return nest.random.lognormal(
                mean=mu,
                std=sigma,
            )

        raise NotImplementedError(f"Unsupported distribution: {weight.distribution}")

    def create_delay_parameter(self, delay):
        if delay.distribution == "fixed" or delay.rel_std == 0.0:
            return delay.mean

        std = delay.mean * delay.rel_std
        min_delay = nest.resolution - 0.5 * nest.resolution

        if delay.distribution == "normal":
            distribution = nest.random.normal(
                mean=delay.mean,
                std=std,
            )

        elif delay.distribution == "lognormal":
            variance = std**2
            sigma_squared = np.log1p(variance / delay.mean**2)
            sigma = np.sqrt(sigma_squared)
            mu = np.log(delay.mean) - 0.5 * sigma_squared

            distribution = nest.random.lognormal(
                mean=mu,
                std=sigma,
            )

        else:
            raise ValueError(f"Unsupported delay distribution: {delay.distribution!r}")

        return nest.math.redraw(
            distribution,
            min=min_delay,
            max=float("inf"),
        )

    def get_spike_events(
        self,
        population: str,
    ) -> dict:
        """
        Return spike events for one population as {"senders": ..., "times": ...}.

        Transparently reads back from ascii files when the recorder is in
        ascii mode (n_events stays available from NEST regardless of mode,
        but the events themselves are only kept in memory in memory mode).
        """

        sr = self.spike_recorders[population]

        if sr.get("record_to") == "ascii":
            return self._read_ascii_spike_events(population)

        return sr.get("events")

    def _read_ascii_spike_events(self, population: str) -> dict:
        """
        Read back the ascii files NEST wrote for one population, merging
        the per-thread/per-process shards NEST writes under local_num_threads>1.
        """

        senders: list[np.ndarray] = []
        times: list[np.ndarray] = []

        for path in sorted(self._recordings_dir.glob(f"{population}-*.dat")):
            data = pd.read_csv(path, sep="\t", comment="#")
            senders.append(data["sender"].to_numpy())
            times.append(data["time_ms"].to_numpy())

        if not senders:
            return {"senders": np.array([], dtype=int), "times": np.array([], dtype=float)}

        return {
            "senders": np.concatenate(senders).astype(int),
            "times": np.concatenate(times).astype(float),
        }

    def save_recordings(self, run_dir: Path) -> list[Path]:
        """
        Return the spike (and, if enabled, voltage) recording files for
        this run.

        In ascii mode these were already written natively by NEST during
        simulate(); nothing is re-serialized. Spike recorders fall back to
        a CSV written here when in memory mode (no prepare_output() call);
        multimeters have no such fallback -- voltage traces are large
        enough that only the native ascii path is supported, so voltage
        data recorded in memory mode is simply not persisted.
        """

        run_dir = Path(run_dir)
        paths: list[Path] = []

        for pop_name, sr in self.spike_recorders.items():
            if sr.get("record_to") == "ascii":
                paths.extend(sorted(self._recordings_dir.glob(f"{pop_name}-*.dat")))
            else:
                paths.append(self._write_memory_recording_csv(pop_name, run_dir))

        for pop_name, mm in self.multimeters.items():
            if mm.get("record_to") == "ascii":
                paths.extend(sorted(self._recordings_dir.glob(f"{pop_name}_voltage-*.dat")))

        return paths

    def _write_memory_recording_csv(self, pop_name: str, run_dir: Path) -> Path:
        events = self.get_spike_events(pop_name)
        senders = np.asarray(events["senders"], dtype=int)
        times = np.asarray(events["times"], dtype=float)
        order = np.argsort(times)

        recordings_dir = run_dir / "recordings"
        recordings_dir.mkdir(parents=True, exist_ok=True)
        path = recordings_dir / f"{pop_name}_spikes.csv"
        np.savetxt(
            path,
            np.column_stack([senders[order], times[order]]),
            delimiter=",",
            header="sender,time_ms",
            comments="",
            fmt=["%d", "%.3f"],
        )
        return path
