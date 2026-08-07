"""Generate the PD14 connectivity configuration from source data.

This converts the original Potjans & Diesmann (2014) connection
probabilities into absolute synapse numbers and writes a connectivity
YAML in the format used by Microcircuit Lab. Only ``connectivity.yaml``
is derived here; the other PD14 network files (populations, neurons,
inputs, scaling, reference) are static and checked in directly.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from microcircuit_lab.models.pd14.data import (
    populations,
    full_num_neurons,
    connection_probabilities,
)
from microcircuit_lab.network.connectivity import num_synapses_from_conn_prob
from microcircuit_lab.io.files import flow_records, write_yaml


def _build_connectivity() -> dict[str, Any]:
    connections: list[dict[str, Any]] = []

    for target_index, target in enumerate(populations):
        for source_index, source in enumerate(populations):
            n_synapses = num_synapses_from_conn_prob(
                connection_probabilities[target_index, source_index],
                full_num_neurons[source_index],
                full_num_neurons[target_index],
            )

            if source.endswith("_E"):
                weight_mean = 0.15
                delay_mean = 1.5
            else:
                weight_mean = -0.60
                delay_mean = 0.75

            # PD14 doubles the L4_E -> L23_E PSP relative to other excitatory connections.
            if source == "L4_E" and target == "L23_E":
                weight_mean = 0.30

            connections.append(
                {
                    "source": source,
                    "target": target,
                    "n_synapses": n_synapses,
                    "weight": {
                        "mean": weight_mean,
                        "rel_std": 0.1,
                        "distribution": "normal",
                    },
                    "delay": {
                        "mean": delay_mean,
                        "rel_std": 0.5,
                        "distribution": "normal",
                    },
                }
            )

    return {"connections": connections}


def generate_pd14_connectivity(
    *,
    config_dir: str | Path = "configs",
    network_name: str = "pd14",
) -> Path:
    """Write ``connectivity.yaml`` for the PD14 network and return its path."""

    output_path = Path(config_dir) / "network" / network_name / "connectivity.yaml"
    connectivity = _build_connectivity()
    write_yaml(output_path, {"connections": flow_records(connectivity["connections"])})
    return output_path


def _add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config-dir", default="configs")
    parser.add_argument("--network-name", default="pd14")


def _run(args: argparse.Namespace) -> None:
    output_path = generate_pd14_connectivity(
        config_dir=args.config_dir,
        network_name=args.network_name,
    )
    print(f"Generated connectivity config: {output_path}")
    print(
        "Other PD14 network files (populations, neurons, inputs, scaling, "
        "reference) are static and were not regenerated."
    )


def add_cli(subparser: argparse.ArgumentParser) -> None:
    """Register PD14 generation arguments on a ``scripts/generate.py`` subparser."""

    _add_arguments(subparser)
    subparser.set_defaults(func=_run)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the PD14 connectivity.yaml from connection-probability source data.",
    )
    _add_arguments(parser)
    args = parser.parse_args()
    _run(args)


if __name__ == "__main__":
    main()
