"""Microcircuit Lab: build, simulate and analyse spiking network models.

The usual entry points::

    from microcircuit_lab import Simulation, load_network

    simulation = Simulation.from_yaml(network_name="pd14")
    simulation.run()

    network = load_network("configs/network/pd14")   # the network ready to simulate
"""

from microcircuit_lab.network import load_network, prepare_network, read_network
from microcircuit_lab.simulation import Simulation

__all__ = ["Simulation", "load_network", "prepare_network", "read_network"]
