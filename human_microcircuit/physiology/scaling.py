"""
Scaling utilities.

Pure mathematical functions used by ParameterBuilder.
"""

from __future__ import annotations


def scale_neuron_number(
    value: int,
    factor: float,
) -> int:
    """
    Scale the number of neurons.
    """

    return int(round(value * factor))


def scale_synapse_number(
    value: int,
    factor: float,
) -> int:
    """
    Scale the number of synapses.
    """

    return int(round(value * factor))


def scale_weight(
    value: float,
    factor: float,
) -> float:
    """
    Scale synaptic weight.

    Potjans convention:
        J -> J / K
    """

    return value / factor
