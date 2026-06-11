"""
Scaling utilities for the human microcircuit.

This module contains purely mathematical transformations and is
independent of any simulator backend.
"""

from __future__ import annotations


def scale_neuron_number(
    n_neurons: int,
    scaling: float,
) -> int:
    """
    Scale the number of neurons.

    Parameters
    ----------
    n_neurons
        Original number of neurons.

    scaling
        Scaling factor.

    Returns
    -------
    int
        Scaled number of neurons.
    """

    return int(round(n_neurons * scaling))


def scale_synapse_number(
    n_synapses: int,
    scaling: float,
) -> int:
    """
    Scale the number of synapses.
    """

    return int(round(n_synapses * scaling))


def scale_weight(
    weight: float,
    k_scaling: float,
) -> float:
    """
    Scale synaptic weight to preserve mean input.

    This follows the Potjans-Diesmann convention.
    """

    return weight / k_scaling
