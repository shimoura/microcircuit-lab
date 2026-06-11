"""
Project entry point.
"""

from human_microcircuit.simulation.simulation import (
    Simulation,
)

import logging
logger = logging.getLogger(__name__)

def main():

    simulation = Simulation.from_yaml()

    simulation.run()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()