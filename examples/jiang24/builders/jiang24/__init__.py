"""Jiang et al. (2024) microcircuit of somatosensory cortex with PV, SOM and VIP interneurons, with static synapses or (``--stp``) short-term plasticity."""

from .build import generate_jiang24, main

__all__ = ["generate_jiang24", "main"]
