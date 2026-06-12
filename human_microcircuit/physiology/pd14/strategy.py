"""
PD14 physiology strategy.
"""
# NOTE:
# This strategy is intentionally introduced as a no-op.
# PD14-specific transformations will be migrated here
# incrementally without changing external behavior.

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
        """
        Apply PD14-specific parameter derivation.

        Subclasses and future implementations may
        progressively move PD14-specific transformations
        into this strategy.
        """

        return network
