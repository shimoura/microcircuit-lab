"""
NEST simulator backend.
This module contains the NestBackend class, which is responsible for
initializing the NEST kernel and managing the simulation lifecycle.
"""

from __future__ import annotations

import nest

from human_microcircuit.network.network import Network


class NestBackend:
    """
    NEST simulator backend.
    """

    def __init__(self, network: Network) -> None:
        self._network = network

    def initialize(self) -> None:
        """Initialize the NEST kernel."""

        nest.ResetKernel()