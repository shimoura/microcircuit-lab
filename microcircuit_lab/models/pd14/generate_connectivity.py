"""
Generate the canonical PD14 connectivity.yaml.

This script converts the original PD14 connection probabilities into
absolute synapse numbers and writes a connectivity YAML in the format
used by human-microcircuit.
"""

from math import log

import numpy as np

from microcircuit_lab.models.pd14.data import (
    populations,
    full_num_neurons,
    connection_probabilities,
)

# ---------------------------------------------------------------------
# Formula from Potjans & Diesmann (2014)
# ---------------------------------------------------------------------


def num_synapses_from_conn_prob(
    conn_prob: float,
    n_source: int,
    n_target: int,
) -> int:
    if conn_prob <= 0.0:
        return 0

    prod = n_source * n_target

    return round(log(1.0 - conn_prob) / log((prod - 1.0) / prod))


# ---------------------------------------------------------------------
# YAML generation
# ---------------------------------------------------------------------

print("connections:")

for target_index, target in enumerate(populations):
    for source_index, source in enumerate(populations):
        n_synapses = num_synapses_from_conn_prob(
            connection_probabilities[target_index, source_index],
            full_num_neurons[source_index],
            full_num_neurons[target_index],
        )

        # -----------------------------
        # Excitatory / inhibitory
        # -----------------------------

        if source.endswith("_E"):
            weight_mean = 0.15
            delay_mean = 1.5
        else:
            weight_mean = -0.60
            delay_mean = 0.75

        # -----------------------------
        # Special PD14 exception:
        #
        # L4_E -> L23_E
        # doubled PSP
        # -----------------------------

        if source == "L4_E" and target == "L23_E":
            weight_mean = 0.30

        print()
        print(f"  - source: {source}")
        print(f"    target: {target}")
        print()
        print(f"    n_synapses: {n_synapses}")
        print()
        print("    weight:")
        print(f"      mean: {weight_mean}")
        print("      rel_std: 0.1")
        print("      distribution: normal")
        print()
        print("    delay:")
        print(f"      mean: {delay_mean}")
        print("      rel_std: 0.5")
        print("      distribution: normal")
