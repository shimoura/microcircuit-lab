"""
Main entry point for the human microcircuit simulation.
"""

import logging
logger = logging.getLogger(__name__)


from human_microcircuit.builders.config_builder import ConfigBuilder
from human_microcircuit.builders.parameter_builder import ParameterBuilder
from human_microcircuit.network.simulation import Simulation
from human_microcircuit.config.simulation import SimulationConfig


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

    simulation = Simulation(
        network_config=network_config,
        simulation_config=simulation_config,
    )

    simulation.build()

    simulation.simulate()

    simulation.print_statistics()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    main()
