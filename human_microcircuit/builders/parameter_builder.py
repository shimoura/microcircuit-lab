"""
Parameter derivation.

This module derives simulator-ready parameters from the biological
network description.
"""

from __future__ import annotations

from human_microcircuit.config.network import NetworkConfig


class ParameterBuilder:
    """
    Derive simulator-ready parameters.
    """

    def __init__(
        self,
        network_config: NetworkConfig,
    ) -> None:

        self._network_config = network_config

    def build(self) -> NetworkConfig:
        """
        Build a derived NetworkConfig.
        """

        #
        # Future:
        #
        # - PSP -> PSC
        # - N scaling
        # - K scaling
        # - DC compensation
        #

        network = self._network_config

        network = self._convert_psp_to_psc(network)

        network = self._apply_scaling(network)

        network = self._apply_dc_compensation(network)

        return network

    def _convert_psp_to_psc(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:

        #
        # Placeholder.
        #
        return network

    def _apply_scaling(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:

        return network

    def _apply_dc_compensation(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:

        return network