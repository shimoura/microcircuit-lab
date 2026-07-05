"""
NEST backend.

This module contains the first implementation of the simulator backend.
"""

from __future__ import annotations

import nest
import numpy as np
import logging

logger = logging.getLogger(__name__)

from microcircuit_lab.network.model import Network
from microcircuit_lab.config.simulation import SimulationConfig
from microcircuit_lab.config.network import PopulationConfig


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

        self.populations: dict[str, nest.NodeCollection] = {}
        self.poisson_generators: dict[str, nest.NodeCollection] = {}
        self.spike_recorders: dict[str, nest.NodeCollection] = {}
        self.multimeters: dict[str, nest.NodeCollection] = {}
        self.devices: dict[str, nest.NodeCollection] = {}

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

    def build(self) -> None:
        """
        Build the complete network.
        """

        self.initialize()

        self.create_populations()

        self.create_spike_recorders()

        self.connect_spike_recorders()

        self.create_poisson_generators()

        self.connect_poisson_generators()

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
                "Connecting %s -> %s " "(N=%d, weight=%g, delay=%g)",
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
        """

        for pop_name in self.populations:

            sr = nest.Create("spike_recorder")

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

    def create_poisson_generators(self) -> None:
        """
        Create one Poisson generator per configured population.
        """

        logger.info("Creating Poisson generators:")

        for pop_name, input_cfg in self._network.config.inputs.items():

            logger.info(
                "Creating Poisson input for %s (rate=%g Hz)",
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
        Connect Poisson generators to populations.
        """

        for pop_name in self.poisson_generators:

            input_cfg = self._network.config.inputs[pop_name]
            nest.Connect(
                self.poisson_generators[pop_name],
                self.get_population(pop_name),
                syn_spec={
                    "weight": self.create_weight_spec(input_cfg.weight),
                    "delay": self.create_delay_parameter(input_cfg.delay),
                },
            )

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
        """
        Create a NEST delay parameter.
        """

        if delay.rel_std == 0.0:
            return delay.mean

        std = delay.mean * delay.rel_std

        return nest.math.redraw(
            nest.random.normal(
                mean=delay.mean,
                std=std,
            ),
            min=nest.resolution - 0.5 * nest.resolution,
            max=float("inf"),
        )

    def get_spike_events(
        self,
        population: str,
    ) -> dict:
        """
        Return the native NEST spike events for one population.
        """

        return self.spike_recorders[population].get("events")
