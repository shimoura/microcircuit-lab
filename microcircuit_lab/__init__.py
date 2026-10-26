"""Microcircuit Lab: build, simulate and analyse spiking network models.

The usual entry points::

    from microcircuit_lab import Simulation, read_network

    simulation = Simulation.from_yaml(network_name="pd14")
    simulation.run()

    network = read_network("configs/network/pd14")   # the network as written in its files
"""

from microcircuit_lab.network import read_network
from microcircuit_lab.simulation import Simulation

__all__ = ["Simulation", "read_network"]
