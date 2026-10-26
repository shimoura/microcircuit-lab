"""Microcircuit Lab: build, simulate and analyse spiking network models.

The usual entry points::

    from microcircuit_lab import Simulation, read_network, read_run

    simulation = Simulation.from_yaml(network_name="pd14")
    simulation.run()

    network = read_network("configs/network/pd14")   # the network as written in its files

    run = read_run(simulation.output_dir)             # a finished run folder, no simulator needed
    spikes = run.spikes("E")                          # senders and times (ms) of one population
"""

from microcircuit_lab.network import read_network
from microcircuit_lab.run_folder import read_run
from microcircuit_lab.simulation import Simulation

__all__ = ["Simulation", "read_network", "read_run"]
