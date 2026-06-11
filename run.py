"""
Main entry point for the human microcircuit simulation.
"""

from human_microcircuit.backend.nest.backend import NestBackend

from human_microcircuit.builders.config_builder import ConfigBuilder
from human_microcircuit.builders.parameter_builder import ParameterBuilder

from human_microcircuit.config.simulation import SimulationConfig

from human_microcircuit.network.network import Network

from human_microcircuit.utils.io import (
    read_network_directory,
    read_yaml,
)


def main() -> None:
    """
    Run a simulation.
    """

    # ------------------------------------------------------------------
    # Read configuration files
    # ------------------------------------------------------------------
    simulation_data = read_yaml("configs/simulation.yaml")
    network_files = read_network_directory("configs/network")
    
    # ------------------------------------------------------------------
    # Build immutable configuration objects
    # ------------------------------------------------------------------
    simulation_config = SimulationConfig.model_validate(simulation_data)

    network_config = ConfigBuilder(
        network_files=network_files,
    ).build()

    # ------------------------------------------------------------------
    # Derive parameters
    # ------------------------------------------------------------------
    network_config = ParameterBuilder(network_config).build()

    # ------------------------------------------------------------------
    # Build simulator-independent network
    # ------------------------------------------------------------------
    network = Network(network_config)

    # ------------------------------------------------------------------
    # Create backend
    # ------------------------------------------------------------------
    backend = NestBackend(
        network=network,
        simulation_config=simulation_config,
    )

    # ------------------------------------------------------------------
    # Build and simulate
    # ------------------------------------------------------------------
    backend.build()
    backend.simulate()

    # ------------------------------------------------------------------
    # Print statistics
    # ------------------------------------------------------------------
    backend.print_statistics()


if __name__ == "__main__":
    main()
