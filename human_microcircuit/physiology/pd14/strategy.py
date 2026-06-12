"""
PD14 physiology strategy.
"""

from __future__ import annotations

from human_microcircuit.config.network import (
    NetworkConfig,
)

from human_microcircuit.physiology.strategy import (
    PhysiologyStrategy,
)


class PD14Strategy(PhysiologyStrategy):
    """
    Physiology strategy implementing the
    Potjans & Diesmann (2014) derivation.
    """

    def derive(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        return network
