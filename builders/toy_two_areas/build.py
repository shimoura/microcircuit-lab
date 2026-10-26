"""Generate the two-area toy network configuration from ``data.py``.

Writes ``configs/network/toy_two_areas/``: populations named
``<area>__<layer>_<cell type>``, one neuron entry per row of ``data.NEURONS``,
connections within and between the areas from the probability rules, Poisson
background input and the full-scale reference rates.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from builders.toy_two_areas import data
from microcircuit_lab.builder_tools import (
    delay,
    num_synapses_from_conn_prob,
    psp_to_psc_iaf_psc_exp,
    scale_network,
    weight,
    write_network,
    write_network_directory,
)
from microcircuit_lab.config.network import NetworkConfig


def population_name(area: str, layer: str, cell_type: str) -> str:
    return f"{area}__{layer}_{cell_type}"


def build_populations() -> list[dict[str, Any]]:
    return [
        {
            "name": population_name(area, layer, cell_type),
            "size": size,
            "neuron": neuron,
            "initial_state": {
                "V_m": {"distribution": "normal", "mean": data.V0_MEAN, "std": data.V0_STD}
            },
            "background_indegree": data.K_EXT[cell_type],
        }
        for area, layer, cell_type, size, neuron in data.POPULATIONS
    ]


def build_neurons() -> dict[str, dict[str, Any]]:
    return {
        name: {"model": data.NEURON_MODEL, "parameters": {**data.BASE_NEURON, **changes}}
        for name, changes in data.NEURONS.items()
    }


def current(psp: float, neuron: str) -> float:
    """The current amplitude (pA) of a PSP amplitude (mV) onto the neuron entry
    ``neuron``: the toy gives its weights as PSPs, and iaf_psc_exp takes
    currents. Excitation uses tau_syn_ex, inhibition tau_syn_in."""
    parameters = {**data.BASE_NEURON, **data.NEURONS[neuron]}
    return psp_to_psc_iaf_psc_exp(
        psp,
        C_m=parameters["C_m"],
        tau_m=parameters["tau_m"],
        tau_syn=parameters["tau_syn_ex"] if psp >= 0 else parameters["tau_syn_in"],
    )


def connection_probability(source: tuple, target: tuple) -> float:
    source_area, source_layer, source_type = source[:3]
    target_area, target_layer, target_type = target[:3]

    if source_area == target_area:
        layer = "same" if source_layer == target_layer else "other"
        return data.P_LOCAL[source_type][target_type] * data.LAYER_FACTOR[layer]

    if source_type in data.EXCITATORY_TYPES:
        return data.P_INTER_AREA.get(target_type, 0.0)
    return 0.0


def delay_mean(source: tuple, target: tuple) -> float:
    if source[0] != target[0]:
        return data.DISTANCE_MM / data.CONDUCTION_SPEED_MM_PER_MS
    return data.DELAY_EXC if source[2] in data.EXCITATORY_TYPES else data.DELAY_INH


def build_connections() -> list[dict[str, Any]]:
    connections: list[dict[str, Any]] = []

    for target in data.POPULATIONS:
        for source in data.POPULATIONS:
            probability = connection_probability(source, target)
            if probability == 0.0:
                continue

            connections.append(
                {
                    "source": population_name(*source[:3]),
                    "target": population_name(*target[:3]),
                    "n_synapses": num_synapses_from_conn_prob(probability, source[3], target[3]),
                    "weight": weight(current(data.PSP[source[2]], target[4]), unit="pA", rel_std=data.WEIGHT_REL_STD),
                    "delay": delay(delay_mean(source, target), rel_std=data.DELAY_REL_STD),
                }
            )

    return connections


def build_background_inputs() -> dict[str, dict[str, Any]]:
    return {
        population_name(area, layer, cell_type): {
            "rate": data.BG_RATE,
            "weight": weight(current(data.BG_PSP, neuron), unit="pA"),
            "delay": delay(data.BG_DELAY),
        }
        for area, layer, cell_type, _, neuron in data.POPULATIONS
    }


def generate_toy_two_areas(
    *,
    config_dir: str | Path = "configs",
    network_name: str = "toy_two_areas",
) -> NetworkConfig:
    """Write ``<config_dir>/network/<network_name>/`` and validate it."""

    return write_network_directory(
        Path(config_dir) / "network" / network_name,
        populations=build_populations(),
        neurons=build_neurons(),
        connections=build_connections(),
        background_inputs=build_background_inputs(),
        reference=data.FULL_MEAN_RATES,
        compact=False,
    )


def main(argv: list[str] | None = None) -> None:
    """Entry point. ``microcircuit-lab generate`` discovers this function (via
    ``builders.toy_two_areas.main``) and forwards it the arguments after the
    model name.
    """
    parser = argparse.ArgumentParser(
        prog="microcircuit-lab generate toy_two_areas",
        description="Generate the two-area toy network configuration.",
    )
    parser.add_argument("--config-dir", default="configs")
    parser.add_argument("--network-name", default=None)
    variant = parser.add_mutually_exclusive_group()
    variant.add_argument(
        "--advanced",
        action="store_true",
        help="write toy_two_areas_advanced instead: values drawn per neuron, connection "
        "rules, synapse models and receptor ports (see advanced.py)",
    )
    variant.add_argument(
        "--clusters",
        type=int,
        metavar="Q",
        help="write toy_two_areas_clustered instead: every population split into Q "
        "clusters (see clustered.py; the other settings are in data.py)",
    )
    parser.add_argument("--n-scaling", type=float, default=1.0, help="multiplies the number of neurons")
    parser.add_argument("--k-scaling", type=float, default=1.0, help="multiplies the synapses per neuron")
    args = parser.parse_args(argv)

    # The builder command of the full-scale network, recorded in scaling.yaml.
    variant = "toy_two_areas" + (f" --clusters {args.clusters}" if args.clusters is not None else "") + (
        " --advanced" if args.advanced else ""
    )
    if args.clusters is not None:
        # imported here: clustered.py builds on the functions of this file
        from builders.toy_two_areas.clustered import generate_toy_two_areas_clustered

        name = args.network_name or "toy_two_areas_clustered"
        network = generate_toy_two_areas_clustered(
            config_dir=args.config_dir, network_name=name, clusters=args.clusters
        )
    elif args.advanced:
        # imported here: advanced.py builds on the functions of this file
        from builders.toy_two_areas.advanced import generate_toy_two_areas_advanced

        name = args.network_name or "toy_two_areas_advanced"
        network = generate_toy_two_areas_advanced(config_dir=args.config_dir, network_name=name)
    else:
        name = args.network_name or "toy_two_areas"
        network = generate_toy_two_areas(config_dir=args.config_dir, network_name=name)

    folder = Path(args.config_dir) / "network" / name
    # A scaled network is written scaled: its files hold the numbers that are
    # simulated, and scaling.yaml records how they were made.
    if args.n_scaling != 1.0 or args.k_scaling != 1.0:
        scaled = scale_network(network, N_scaling=args.n_scaling, K_scaling=args.k_scaling, scaled_from=variant)
        write_network(scaled, folder, compact=False)
    print(f"Generated and validated {folder}")


if __name__ == "__main__":
    main()
