"""Generate the Jiang et al. (2024) network configuration from ``data.py``.

Writes ``configs/network/jiang24/``: the publication's Base model, with static
synapses. It has 13 populations (E, PV and SOM cells in L2/3, L4, L5 and L6, and
VIP cells in L2/3), neuron parameters per cell type, connections made pair by
pair with a probability per projection, lognormal weights and delays, and one
Poisson background train per neuron. The weights are given as PSPs (mV) and
written as the currents (pA) that give them with each target's neuron.

Also writes ``configs/simulation/jiang24.yaml``, with the publication's duration
and time step, on which the delays depend, and ``configs/analysis/jiang24.yaml``,
which switches on the plots of Fig. 6A (``analyses/jiang24_*.py``).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from builders.jiang24 import data
from microcircuit_lab.builder_tools import (
    delay,
    psp_to_psc_iaf_psc_exp,
    weight,
    write_network_directory,
)
from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.config.yaml_files import write_yaml


def _cell_type(population: str) -> str:
    return population.split("_")[1]


def _current(psp: float, neuron: str) -> float:
    """The current amplitude (pA) of a PSP amplitude (mV) onto the neuron entry
    ``neuron``. Excitation uses tau_syn_ex, inhibition tau_syn_in."""
    return psp_to_psc_iaf_psc_exp(
        psp,
        C_m=data.neurons[neuron]["C_m"],
        tau_m=data.neurons[neuron]["tau_m"],
        tau_syn=data.tau_syn_ex if psp > 0 else data.tau_syn_in,
    )


def _build_populations() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "size": size,
            "neuron": neuron,
            "initial_state": {"V_m": {"distribution": "normal", "mean": data.V0_mean, "std": data.V0_std}},
        }
        for name, size, neuron in data.populations
    ]


def _build_neurons() -> dict[str, dict[str, Any]]:
    return {
        name: {
            "model": data.neuron_model,
            "parameters": {
                **parameters,
                "V_reset": parameters["E_L"],
                "tau_syn_ex": data.tau_syn_ex,
                "tau_syn_in": data.tau_syn_in,
                "t_ref": data.t_ref,
                "I_e": 0.0,
            },
        }
        for name, parameters in data.neurons.items()
    }


def _build_connections() -> list[dict[str, Any]]:
    connections: list[dict[str, Any]] = []

    for target_index, (target, _, target_neuron) in enumerate(data.populations):
        for source_index, (source, _, _) in enumerate(data.populations):
            probability = data.connection_probabilities[target_index][source_index]
            if probability == 0.0:
                continue

            if _cell_type(source) == "E":
                psp, delay_mean, delay_std = data.psp_exc, data.delay_exc_mean, data.delay_exc_std
            else:
                psp, delay_mean, delay_std = data.g * data.psp_exc, data.delay_inh_mean, data.delay_inh_std

            connections.append(
                {
                    "source": source,
                    "target": target,
                    "rule": "pairwise_bernoulli",
                    "p": probability,
                    "weight": weight(
                        _current(psp, target_neuron),
                        unit="pA",
                        rel_std=data.weight_rel_std,
                        distribution="lognormal",
                    ),
                    "delay": delay(
                        delay_mean,
                        rel_std=delay_std / delay_mean,
                        distribution="lognormal",
                        lower_bound=data.delay_min,
                        bound_mode="redraw",
                    ),
                }
            )

    return connections


def _build_poisson_background() -> dict[str, dict[str, Any]]:
    return {
        name: {
            "rate": data.bg_rate[_cell_type(name)],
            "indegree": data.bg_indegree,
            "weight": weight(_current(data.bg_psp, neuron), unit="pA"),
            "delay": delay(data.bg_delay),
        }
        for name, _, neuron in data.populations
    }


def generate_jiang24(*, config_dir: str | Path = "configs", network_name: str = "jiang24") -> NetworkConfig:
    """Write ``<config_dir>/network/<network_name>/``, validate it, and write
    ``<network_name>.yaml`` in ``<config_dir>/simulation/`` and ``<config_dir>/analysis/``."""

    write_yaml(
        Path(config_dir) / "simulation" / f"{network_name}.yaml",
        {
            "t_sim": data.t_sim,
            "resolution": data.resolution,
            "rng_seed": data.rng_seed,
            "local_num_threads": data.local_num_threads,
        },
    )
    write_yaml(
        Path(config_dir) / "analysis" / f"{network_name}.yaml",
        {
            "style": {"color_mode": "cell_type", "cell_type_colors": data.cell_type_colors},
            "jiang24_raster": {"enabled": True, "begin": data.raster_begin, "end": data.raster_end},
            "jiang24_firing_rates": {
                "enabled": True,
                "begin": data.analysis_begin,
                "end": data.analysis_end,
                "experiment": data.experiment_rates,
            },
        },
    )
    return write_network_directory(
        Path(config_dir) / "network" / network_name,
        populations=_build_populations(),
        neurons=_build_neurons(),
        connections=_build_connections(),
        poisson_background=_build_poisson_background(),
        reference=data.full_mean_rates,
        compact=False,
    )


def main(argv: list[str] | None = None) -> None:
    """Entry point of ``microcircuit-lab generate jiang24``."""
    parser = argparse.ArgumentParser(
        prog="microcircuit-lab generate jiang24",
        description="Generate the Jiang et al. (2024) network configuration from its published parameters.",
    )
    parser.add_argument("--config-dir", default="configs")
    parser.add_argument("--network-name", default="jiang24")
    args = parser.parse_args(argv)

    generate_jiang24(config_dir=args.config_dir, network_name=args.network_name)
    print(f"Generated and validated {Path(args.config_dir) / 'network' / args.network_name}")
    print(f"Generated {Path(args.config_dir) / 'simulation' / args.network_name}.yaml")
    print(f"Generated {Path(args.config_dir) / 'analysis' / args.network_name}.yaml")


if __name__ == "__main__":
    main()
