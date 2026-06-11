"""
NEST backend.

This module contains the first implementation of the simulator backend.
"""

from __future__ import annotations

import nest

import logging

logger = logging.getLogger(__name__)

from human_microcircuit.network.network import Network
from human_microcircuit.config.simulation import SimulationConfig
from human_microcircuit.config.network import PopulationConfig


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
                    "weight": self.create_weight_parameter(connection.weight),
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

        for pop_name, input_cfg in self._network.config.inputs.items():

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
                    "weight": self.create_weight_parameter(input_cfg.weight),
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

        logger.info("Printing simulation statistics:")
        logger.info("Simulation statistics")
        logger.info("---------------------")

        for pop_name in self.spike_recorders:
            sr = self.spike_recorders[pop_name]
            logger.info(
                "%s: %d spikes",
                pop_name,
                sr.n_events,
            )

    def create_weight_parameter(
        self,
        weight,
    ):
        """
        Create a NEST weight parameter.

        Currently returns a constant value.

        Future:
            - normal distribution
            - lognormal distribution
            - redraw
        """

        return weight.mean

    def create_delay_parameter(
        self,
        delay,
    ):
        """
        Create a NEST delay parameter.

        Currently returns a constant value.

        Future:
            - normal distribution
            - lognormal distribution
            - redraw
        """

        return delay.mean
