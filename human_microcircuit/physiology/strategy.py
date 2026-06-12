"""
Interfaces for physiology-specific parameter derivation.
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod

from human_microcircuit.config.network import (
    NetworkConfig,
)


class PhysiologyStrategy(ABC):
    """
    Base interface for physiology-specific parameter derivation.
    """

    @abstractmethod
    def derive(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        """
        Derive simulator-ready parameters from a biological network.
        """
        raise NotImplementedError
