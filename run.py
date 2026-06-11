from pathlib import Path

from human_microcircuit.utils.io import read_network_directory
from human_microcircuit.utils.io import read_yaml

from human_microcircuit.builders.config_builder import ConfigBuilder
from human_microcircuit.builders.parameter_builder import ParameterBuilder

from human_microcircuit.network.network import Network
from human_microcircuit.backend.nest.backend import NestBackend

def main() -> None:

    simulation_data = read_yaml("configs/simulation.yaml")

    network_data = read_network_directory(
        "configs/network"
    )

    network_config = ConfigBuilder(
        populations_data=network_data["populations"],
        neurons_data=network_data["neurons"],
        connectivity_data=network_data["connectivity"],
        inputs_data=network_data["inputs"],
        scaling_data=network_data["scaling"],
    ).build()

    network_config = ParameterBuilder(network_config).build()

    print()

    print("Configuration successfully loaded.")

    print()

    print(network_config)

    network = Network(network_config)

    backend = NestBackend(network)

    backend.initialize()

    print("NEST initialized successfully.")


if __name__ == "__main__":
    main()