"""
High-level simulation orchestration.
"""

from __future__ import annotations

from human_microcircuit.backend.nest.backend import NestBackend
from human_microcircuit.config.network import NetworkConfig
from human_microcircuit.config.simulation import SimulationConfig
from human_microcircuit.network.network import Network


class Simulation:
    """
    High-level simulation object.

    This class owns the biological network and delegates simulator-specific
    operations to the backend.
    """

    def __init__(
        self,
        network_config: NetworkConfig,
        simulation_config: SimulationConfig,
    ) -> None:

        self.network = Network(network_config)

        self.backend = NestBackend(
            network=self.network,
            simulation_config=simulation_config,
        )

    def build(self) -> None:
        """
        Build the simulation.
        """

        self.backend.build()

    def simulate(self) -> None:
        """
        Run the simulation.
        """

        self.backend.simulate()

    def print_statistics(self) -> None:
        """
        Print simulation statistics.
        """

        self.backend.print_statistics()