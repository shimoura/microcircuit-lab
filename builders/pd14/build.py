"""Generate the PD14 network configuration from source data.

Turns the Potjans & Diesmann (2014) parameters in ``data.py`` into a full
``configs/network/<name>/`` directory: populations, neurons, connectivity
(connection probabilities converted to absolute synapse numbers), background
inputs, scaling and reference rates.

``--background-mode mean_current`` replaces the Poisson background by a constant current
of equal mean, the comparison of the publication's Fig. 5
(``microcircuit-lab generate pd14 --network-name pd14_mean_current --background-mode mean_current``).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from builders.pd14 import data
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


def _neuron_type(population: str) -> str:
    return "excitatory" if population.endswith("_E") else "inhibitory"


def _current(psp: float) -> float:
    """The current amplitude (pA) of a PSP amplitude (mV): PD14 gives its
    weights as PSPs, and NEST's iaf_psc_exp takes currents. All populations
    have the same neuron, and one tau_syn for both signs."""
    return psp_to_psc_iaf_psc_exp(
        psp,
        C_m=data.neuron_params["C_m"],
        tau_m=data.neuron_params["tau_m"],
        tau_syn=data.neuron_params["tau_syn"],
    )


def _build_populations() -> list[dict[str, Any]]:
    return [
        {
            "name": population,
            "size": int(data.full_num_neurons[index]),
            "neuron": _neuron_type(population),
            "initial_state": {
                "V_m": {"distribution": "normal", "mean": data.V0_mean[index], "std": data.V0_std[index]}
            },
            "background_indegree": int(data.K_ext[index]),
        }
        for index, population in enumerate(data.populations)
    ]


def _build_neurons() -> dict[str, dict[str, Any]]:
    params = dict(data.neuron_params)
    tau_syn = params.pop("tau_syn")
    parameters = {**params, "tau_syn_ex": tau_syn, "tau_syn_in": tau_syn, "I_e": 0.0}
    return {
        neuron_type: {"model": data.neuron_model, "parameters": dict(parameters)}
        for neuron_type in ("excitatory", "inhibitory")
    }


def _build_connections() -> list[dict[str, Any]]:
    connections: list[dict[str, Any]] = []

    for target_index, target in enumerate(data.populations):
        for source_index, source in enumerate(data.populations):
            n_synapses = num_synapses_from_conn_prob(
                data.connection_probabilities[target_index, source_index],
                data.full_num_neurons[source_index],
                data.full_num_neurons[target_index],
            )

            if _neuron_type(source) == "excitatory":
                weight_mean = data.PSP_exc_mean
                delay_mean = data.delay_exc_mean
            else:
                weight_mean = data.PSP_exc_mean * data.g
                delay_mean = data.delay_inh_mean

            # PD14 doubles the L4_E -> L23_E PSP relative to other excitatory connections.
            if source == "L4_E" and target == "L23_E":
                weight_mean = 2.0 * data.PSP_exc_mean

            connections.append(
                {
                    "source": source,
                    "target": target,
                    "n_synapses": n_synapses,
                    "weight": weight(_current(weight_mean), unit="pA", rel_std=data.weight_rel_std),
                    "delay": delay(delay_mean, rel_std=data.delay_rel_std),
                }
            )

    return connections


def _build_background_inputs() -> dict[str, dict[str, Any]]:
    return {
        population: {
            "rate": data.bg_rate,
            "weight": weight(_current(data.PSP_exc_mean), unit="pA"),
            "delay": delay(data.delay_poisson),
        }
        for population in data.populations
    }


def generate_pd14(
    *,
    config_dir: str | Path = "configs",
    network_name: str = "pd14",
    background_mode: str = "poisson",
) -> NetworkConfig:
    """Write ``<config_dir>/network/<network_name>/`` for PD14 and validate it."""

    return write_network_directory(
        Path(config_dir) / "network" / network_name,
        populations=_build_populations(),
        neurons=_build_neurons(),
        connections=_build_connections(),
        background_inputs=_build_background_inputs(),
        background_mode=background_mode,
        reference=dict(zip(data.populations, data.full_mean_rates.tolist())),
        compact=False,
    )


def main(argv: list[str] | None = None) -> None:
    """Entry point. ``microcircuit-lab generate`` discovers this function (via
    ``builders.pd14.main``) and forwards it the arguments after the model name.
    """
    parser = argparse.ArgumentParser(
        prog="microcircuit-lab generate pd14",
        description="Generate the PD14 network configuration from its published parameters.",
    )
    parser.add_argument("--config-dir", default="configs")
    parser.add_argument("--network-name", default="pd14")
    parser.add_argument("--background-mode", choices=("poisson", "mean_current"), default="poisson")
    parser.add_argument("--n-scaling", type=float, default=1.0, help="multiplies the number of neurons")
    parser.add_argument("--k-scaling", type=float, default=1.0, help="multiplies the synapses per neuron")
    args = parser.parse_args(argv)

    folder = Path(args.config_dir) / "network" / args.network_name
    network = generate_pd14(
        config_dir=args.config_dir,
        network_name=args.network_name,
        background_mode=args.background_mode,
    )
    # A scaled network is written scaled: its files hold the numbers that are
    # simulated, and scaling.yaml records how they were made.
    if args.n_scaling != 1.0 or args.k_scaling != 1.0:
        scaled_from = "pd14" + (" --background-mode mean_current" if args.background_mode == "mean_current" else "")
        scaled = scale_network(network, N_scaling=args.n_scaling, K_scaling=args.k_scaling, scaled_from=scaled_from)
        write_network(scaled, folder, compact=False)
    print(f"Generated and validated {folder}")


if __name__ == "__main__":
    main()
