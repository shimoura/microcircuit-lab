"""From a network folder to the network the simulator builds.

``load.py`` reads and checks the files and ``prepare.py`` gets the network
ready for the simulation, in these steps:

- ``scaling.py``: fewer neurons and synapses, rescaled weights;
- ``compensation.py``: constant currents for the mean input that scaling or
  ``background_mode: mean_current`` remove;
- ``mean_input.py``: indegrees, mean currents and time constants, used by the
  compensation.
"""

from .load import load_network, read_network
from .prepare import prepare_network

__all__ = ["load_network", "prepare_network", "read_network"]
