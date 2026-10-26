"""From a network folder to the network the simulator builds.

``load.py`` reads and checks the files. Scaling and the constant currents are
in ``builder_tools/``.
"""

from .load import read_network

__all__ = ["read_network"]
