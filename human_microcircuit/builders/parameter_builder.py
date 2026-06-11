"""
Parameter derivation for the network.

The ParameterBuilder is responsible for deriving simulation parameters from
the biological network description.

It must never modify the original NetworkConfig. Instead, it returns a new
NetworkConfig containing the derived parameters.

Typical responsibilities (to be implemented progressively) include:

- PSP -> PSC conversion
- N scaling
- K scaling
- DC compensation
- synaptic weight scaling
- delay scaling
- receptor-density scaling
- other biologically-derived parameter transformations

This module is simulator-independent and must not import NEST or any other
simulation backend.
"""

from __future__ import annotations

from human_microcircuit.config.network import NetworkConfig


class ParameterBuilder:
    """
    Build a derived NetworkConfig from an existing NetworkConfig.

    The input configuration is treated as immutable and is never modified.
    """

    def __init__(self, network_config: NetworkConfig) -> None:
        self._network_config = network_config

    def build(self) -> NetworkConfig:
        """
        Build a derived NetworkConfig.

        At the moment this is simply a pass-through and returns the original
        immutable configuration.

        In future implementations this method will:
            - convert PSP amplitudes to PSC amplitudes
            - apply neuron scaling (N_scaling)
            - apply connectivity scaling (K_scaling)
            - compute DC compensation
            - derive scaled synaptic weights
            - derive scaled delays
            - apply receptor-density corrections
            - perform other parameter transformations

        Returns
        -------
        NetworkConfig
            Derived network configuration.
        """

        return self._network_config