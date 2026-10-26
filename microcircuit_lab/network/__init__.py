"""From a network folder to the network the simulator builds.

``load.py`` reads and checks the files and ``prepare.py`` gets the network
ready for the simulation (the background input, see ``prepare_network``).
Scaling and the constant currents are in ``builder_tools/``.
"""

from .load import load_network, read_network
from .prepare import prepare_network

__all__ = ["load_network", "prepare_network", "read_network"]
