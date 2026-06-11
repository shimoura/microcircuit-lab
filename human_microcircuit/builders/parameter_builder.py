"""
Parameter derivation.
"""

from __future__ import annotations

from copy import deepcopy

from human_microcircuit.config.network import NetworkConfig


class ParameterBuilder:
    """
    Build a simulator-ready NetworkConfig.
    """

    def __init__(
        self,
        network_config: NetworkConfig,
    ) -> None:
        self._network_config = network_config

    def build(self) -> NetworkConfig:
        """
        Build a derived configuration.
        """

        network = deepcopy(self._network_config)
        network = self._apply_scaling(network)

        #
        # Future:
        #
        # network = self._apply_n_scaling(network)
        # network = self._apply_k_scaling(network)
        # network = self._apply_dc_compensation(network)
        #

        return network

    def _apply_scaling(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        """
        Apply network scaling.

        Currently scales:
            - neuron numbers
            - synapse numbers
            - synaptic weights

        DC compensation will be added afterwards.
        """

        #
        # implemented next commit
        #

        return network
