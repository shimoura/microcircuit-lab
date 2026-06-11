"""
Project entry point.
"""

from human_microcircuit.simulation.simulation import (
    Simulation,
)

import logging
logger = logging.getLogger(__name__)

def main():

    simulation = Simulation.from_yaml(
        network_name="pd14",
        simulation_name="default",
    )
    simulation.run()

    events = simulation.get_spike_events("L23_E")

    print(events.keys())

    print(events["senders"][:10])

    print(events["times"][:10])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()