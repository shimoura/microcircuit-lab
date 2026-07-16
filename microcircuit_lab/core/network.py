"""
Simulator-independent network description.
"""

from __future__ import annotations

from microcircuit_lab.core.config.network import NetworkConfig


class Network:
    """
    High-level network object.

    This class owns the immutable NetworkConfig describing the
    biological network.

    It intentionally contains no simulator-specific logic.
    """

    def __init__(
        self,
        config: NetworkConfig,
    ):
        self.config = config