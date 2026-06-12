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
    def apply_psp_to_psc(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        raise NotImplementedError


    @abstractmethod
    def apply_weight_scaling(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        raise NotImplementedError


    @abstractmethod
    def apply_dc_compensation(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        raise NotImplementedError


    @abstractmethod
    def apply_external_poisson_rates(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        raise NotImplementedError