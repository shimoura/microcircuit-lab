"""
Simulator-independent network description.
"""

from __future__ import annotations

from human_microcircuit.config.network import NetworkConfig


class Network:
    """
    High-level network object.

    This class owns the immutable NetworkConfig describing the
    biological network.

    It intentionally contains no simulator-specific logic.
    """

    def __init__(self, config: NetworkConfig) -> None:
        self._config = config

    @property
    def config(self) -> NetworkConfig:
        """Return the immutable network configuration."""
        return self._config