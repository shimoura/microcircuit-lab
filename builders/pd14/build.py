"""Generate the PD14 connectivity configuration from source data.

This converts the original Potjans & Diesmann (2014) connection
probabilities into absolute synapse numbers and writes a connectivity
YAML in the format used by Microcircuit Lab. Only ``connectivity.yaml``
is derived here; the other PD14 network files (populations, neurons,
background_inputs, scaling, reference) are static and checked in directly.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from builders.pd14.data import (
    populations,
    full_num_neurons,
    connection_probabilities,
)
from microcircuit_lab.network.connectivity import num_synapses_from_conn_prob
from microcircuit_lab.io import delay, weight
from microcircuit_lab.io.files import flow_records, write_yaml
from microcircuit_lab.io.network_validation import validate_network_config


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
                    "weight": weight(weight_mean, unit="PSP", rel_std=0.1),
                    "delay": delay(delay_mean, rel_std=0.5),
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
        "Other PD14 network files (populations, neurons, background_inputs, "
        "scaling, reference) are static and were not regenerated."
    )

    network_dir = Path(args.config_dir) / "network" / args.network_name
    if (network_dir / "network.yaml").exists():
        validate_network_config(network_dir)
        print("Validated: config is a usable input to the simulation pipeline.")
    else:
        print(
            f"Skipped validation -- {network_dir} has no network.yaml. Copy the static "
            "PD14 files there (from configs/network/pd14/) before running this network."
        )


def main(argv: list[str] | None = None) -> None:
    """Entry point. ``scripts/generate.py`` discovers this function (via
    ``builders.pd14.main``) and forwards it the
    arguments after the model name.
    """
    parser = argparse.ArgumentParser(
        prog="generate.py pd14",
        description="Generate the PD14 connectivity.yaml from connection-probability source data.",
    )
    _add_arguments(parser)
    _run(parser.parse_args(argv))


if __name__ == "__main__":
    main()
