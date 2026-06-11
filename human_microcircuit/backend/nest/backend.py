"""
NEST backend.

This module contains the first implementation of the simulator backend.

For now it is intentionally simple:
    - initialize kernel
    - create populations
    - create spike recorders
    - create Poisson generators
    - connect Poisson -> populations
    - connect populations -> spike recorders
    - simulate

More advanced functionality (recurrent connectivity, scaling,
PSC conversion, etc.) will be added incrementally.
"""

from __future__ import annotations

import nest

from human_microcircuit.network.network import Network
from human_microcircuit.config.simulation import SimulationConfig


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

    def initialize(self) -> None:
        """
        Initialize the NEST kernel.
        """

        nest.ResetKernel()

        nest.resolution = self._simulation_config.resolution

        nest.local_num_threads = self._simulation_config.local_num_threads

        nest.rng_seed = self._simulation_config.rng_seed

        nest.print_time = self._simulation_config.print_time

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

            nodes.set(pop_cfg.neuron.parameters.model_dump())

            #
            # For now:
            # initialize all neurons with the same membrane potential.
            #
            nodes.V_m = pop_cfg.V0_mean

            self.populations[pop_name] = nodes

    def connect_recurrent_connections(self) -> None:
        """
        Connect populations according to the connectivity configuration.
        """

        print("\nCreating recurrent connections:")

        for connection in self._network.config.connections:

            source = self.populations[connection.source]
            target = self.populations[connection.target]

            print(
                f"  {connection.source} -> {connection.target} "
                f"(N={connection.n_synapses})"
            )
            
            nest.Connect(
                source,
                target,
                conn_spec={
                    "rule": "fixed_total_number",
                    "N": connection.n_synapses,
                },
                syn_spec={
                    "weight": connection.weight.mean,
                    "delay": connection.delay.mean,
                },
            )

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
                self.populations[pop_name],
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
                self.populations[pop_name],
                syn_spec={
                    "weight": input_cfg.weight.mean,
                    "delay": input_cfg.delay.mean,
                },
            )

    def simulate(self) -> None:
        """
        Run the simulation.
        """

        nest.Simulate(
            self._simulation_config.t_sim
        )

    def print_statistics(self) -> None:
        """
        Print simple statistics.
        """

        print()
        print("Simulation statistics")
        print("---------------------")

        for pop_name in self.spike_recorders:

            sr = self.spike_recorders[pop_name]

            print(f"{pop_name}: " f"{sr.n_events} spikes")

        print()
