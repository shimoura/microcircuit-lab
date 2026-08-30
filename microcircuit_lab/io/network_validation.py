"""
Confirm a network config directory is a valid input to the next step.

:func:`validate_network_config` runs exactly what
:meth:`Simulation.from_yaml` runs before the simulator is touched: it
schema-checks every file, resolves the cross-file references, and runs the
preprocessing that derives the simulator-ready form. If it returns without
raising, the directory is a usable network config -- however the files got
there, hand-written or produced by a generator.

This is the contract for the generator path: a generator can be any code
at all, as long as its output passes here.
"""

from __future__ import annotations

from pathlib import Path

from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.io.config import NetworkConfigLoader
from microcircuit_lab.io.files import read_network_directory
from microcircuit_lab.network.preprocessing import NetworkPreprocessor


def validate_network_config(network_dir: str | Path) -> NetworkConfig:
    """Load, assemble and preprocess ``network_dir``; return the resolved config.

    Raises with the offending file and field named (``ValidationError`` for
    a schema problem, ``ValueError`` for an unresolved reference or an
    inconsistency the preprocessing step catches) if the directory is not a
    usable network config.
    """

    directory = read_network_directory(Path(network_dir))
    config = NetworkConfigLoader(directory).build()
    return NetworkPreprocessor(config).process()
