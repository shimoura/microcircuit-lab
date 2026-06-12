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

    def apply_psp_to_psc(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        return network

    def apply_weight_scaling(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        return network

    def apply_dc_compensation(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        return network

    def apply_external_poisson_rates(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        return network
