"""
Project entry point.
"""

from microcircuit_lab.simulation.simulation import (
    Simulation,
)
from microcircuit_lab.analysis.raster import plot_raster


import logging
logger = logging.getLogger(__name__)

def main():

    simulation = Simulation.from_yaml(
        network_name="pd14",
        simulation_name="default",
    )
    simulation.run()
    plot_raster(simulation)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()