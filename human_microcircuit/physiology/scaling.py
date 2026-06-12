"""
Scaling utilities.

Pure mathematical functions used by ParameterBuilder.
"""

from __future__ import annotations
import math


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


def scale_weight_sqrt(
    weight: float,
    K_scaling: float,
) -> float:
    """
    Scale synaptic weights according to Potjans & Diesmann (2014).

    Scaling preserves input fluctuations by applying

        w -> w / sqrt(K_scaling)
    """

    return weight / math.sqrt(K_scaling)