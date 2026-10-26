"""The two-area toy with every population split into clusters.

Writes ``configs/network/toy_two_areas_clustered/``: the network of
``toy_two_areas`` (see ``build.py``), each population split into Q clusters
(``data.CLUSTERS``), named ``<population>__c<i>`` (``A__L23_E__c0``). The rule
is a common one for clustered networks:

* **Sizes:** each cluster has ceil(N / Q) neurons (200 into 3: 67 each).
* **Synapses:** each connection is split over every pair of a source and a
  target cluster, ceil(n_synapses / Q²) each.
* **Weights:** E -> E weights are multiplied by ``J_E_plus`` within a cluster
  (cluster i to cluster i) and by ``J_E_minus = (Q - J_E_plus) / (Q - 1)``
  between clusters; the weights of every connection with an inhibitory source
  or target by ``J_I_plus = 1 + R_J (J_E_plus - 1)`` and
  ``J_I_minus = (Q - J_I_plus) / (Q - 1)``. These minus factors keep each
  neuron's mean input as in ``toy_two_areas``.
* **Between areas:** the same rule with its own ``J_E_plus`` and ``R_J``;
  cluster i of one area is "the same cluster" as cluster i of the other.
* **Background:** every neuron keeps its background indegree; the clusters of
  a population share one Poisson generator (``generator:`` in
  ``background_inputs.yaml``), and each neuron still gets its own spike train.

It is written at full scale, with no reference rates, as the advanced
variant.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from builders.toy_two_areas import data
from builders.toy_two_areas.build import (
    build_background_inputs,
    build_connections,
    build_neurons,
    build_populations,
)
from microcircuit_lab.builder_tools import write_network_directory
from microcircuit_lab.config.network import NetworkConfig


def cluster_name(population: str, cluster: int) -> str:
    return f"{population}__c{cluster}"


def weight_factors(clusters: int, j_e_plus: float, r_j: float) -> dict[tuple[bool, bool], float]:
    """The weight factor of each kind of connection, as
    ``{(E -> E?, same cluster?): factor}``."""

    if not 0.0 <= j_e_plus < clusters:
        raise ValueError(
            f"J_E_plus = {j_e_plus} needs to be at least 0 and below the number of clusters "
            f"({clusters}); otherwise the weights between clusters would change sign."
        )
    j_i_plus = 1 + r_j * (j_e_plus - 1)
    return {
        (True, True): j_e_plus,
        (True, False): (clusters - j_e_plus) / (clusters - 1),
        (False, True): j_i_plus,
        (False, False): (clusters - j_i_plus) / (clusters - 1),
    }


def is_excitatory(population: str) -> bool:
    return population.split("_")[-1] in data.EXCITATORY_TYPES


def clustered_populations(clusters: int) -> list[dict[str, Any]]:
    return [
        {**population, "name": cluster_name(population["name"], i),
         "size": math.ceil(population["size"] / clusters)}
        for population in build_populations()
        for i in range(clusters)
    ]


def clustered_connections(
    clusters: int, within: dict[tuple[bool, bool], float], between: dict[tuple[bool, bool], float]
) -> list[dict[str, Any]]:
    connections = []
    for connection in build_connections():
        source, target = connection["source"], connection["target"]
        factors = within if source.split("__")[0] == target.split("__")[0] else between
        e_to_e = is_excitatory(source) and is_excitatory(target)
        for i in range(clusters):
            for k in range(clusters):
                weight = dict(connection["weight"])
                weight["mean"] = connection["weight"]["mean"] * factors[(e_to_e, i == k)]
                connections.append({
                    **connection,
                    "source": cluster_name(source, k),
                    "target": cluster_name(target, i),
                    "n_synapses": math.ceil(connection["n_synapses"] / clusters**2),
                    "weight": weight,
                })
    return connections


def clustered_background_inputs(clusters: int) -> dict[str, dict[str, Any]]:
    """The background input of each cluster: its population's, through one
    generator shared by the population's clusters."""
    return {
        cluster_name(population, i): {**entry, "generator": population}
        for population, entry in build_background_inputs().items()
        for i in range(clusters)
    }


def generate_toy_two_areas_clustered(
    *,
    config_dir: str | Path = "configs",
    network_name: str = "toy_two_areas_clustered",
    clusters: int = data.CLUSTERS,
) -> NetworkConfig:
    """Write ``<config_dir>/network/<network_name>/`` and validate it."""

    if clusters < 2:
        raise ValueError(f"clusters = {clusters}: a population needs at least 2 clusters.")
    within = weight_factors(clusters, data.J_E_PLUS, data.R_J)
    between = weight_factors(clusters, data.BETWEEN_AREAS_J_E_PLUS, data.BETWEEN_AREAS_R_J)
    return write_network_directory(
        Path(config_dir) / "network" / network_name,
        populations=clustered_populations(clusters),
        neurons=build_neurons(),
        connections=clustered_connections(clusters, within, between),
        background_inputs=clustered_background_inputs(clusters),
    )
