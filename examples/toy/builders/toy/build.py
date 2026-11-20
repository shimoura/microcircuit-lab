"""Write the toy network from Python: the smallest example of a builder.

``configs/network/toy/`` holds the same network, written by hand with comments,
for editing the YAML files directly. This builder writes it to
``configs/network/toy_from_builder/``, so the commented files are never
replaced. Run it with the toy's simulation and analysis settings::

    microcircuit-lab generate toy
    microcircuit-lab run --network toy_from_builder --simulation toy --analysis toy

A new builder can start from a copy of this one: change the values, then the
names.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from microcircuit_lab.builder_tools import (
    delay,
    psp_to_psc_iaf_psc_exp,
    weight,
    write_network_directory,
    zero_bound,
)
from microcircuit_lab.config.network import NetworkConfig

# A small excitatory/inhibitory recurrent network in the spirit of Brunel
# (2000): sparse random connectivity, inhibition 4x stronger than excitation,
# driven by strong Poisson background input. It spikes at about 20 spikes/s
# per population.
sizes = {"E": 800, "I": 200}

# NEST's iaf_psc_exp; its parameters are passed to the simulator as they are.
neuron_model = "iaf_psc_exp"
neuron_parameters = {
    "C_m": 250.0,
    "tau_m": 10.0,
    "tau_syn_ex": 0.5,
    "tau_syn_in": 0.5,
    "E_L": -65.0,
    "V_reset": -65.0,
    "V_th": -50.0,
    "t_ref": 2.0,
    "I_e": 0.0,
}

# The weights are chosen as PSP amplitudes (mV); the files hold the currents
# (pA) that iaf_psc_exp takes, converted once here.
psp_e = 0.15
psp_i = -0.6
delay_e = 1.5
delay_i = 0.75

# Drawn weights keep their sign and drawn delays stay at delay_min (ms) or
# more, both drawn again past the bound. delay_min is half the 0.1 ms time
# step: a shorter delay would round to 0 steps.
bound_mode = "redraw"
delay_min = 0.05

# Synapses of each connection (source, target).
synapses = {("E", "E"): 64000, ("I", "E"): 16000, ("E", "I"): 16000, ("I", "I"): 4000}

# Background: each neuron gets INDEGREE Poisson synapses firing at RATE (spikes/s).
background_rate = 8.0
background_indegree = 1000


def _current(psp: float) -> float:
    """The current (pA) of a PSP amplitude (mV) for the toy's neuron."""
    return psp_to_psc_iaf_psc_exp(
        psp,
        C_m=neuron_parameters["C_m"],
        tau_m=neuron_parameters["tau_m"],
        tau_syn=neuron_parameters["tau_syn_ex"],
    )


def _neuron(population: str) -> str:
    return "excitatory" if population == "E" else "inhibitory"


def _populations() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "size": size,
            "neuron": _neuron(name),
            # The membrane potential at the start, drawn per neuron.
            "initial_state": {"V_m": {"distribution": "normal", "mean": -65.0, "std": 5.0}},
        }
        for name, size in sizes.items()
    ]


def _connections() -> list[dict[str, Any]]:
    connections = []
    for (source, target), n_synapses in synapses.items():
        psp, delay_mean = (psp_e, delay_e) if source == "E" else (psp_i, delay_i)
        connections.append(
            {
                "source": source,
                "target": target,
                "n_synapses": n_synapses,
                "weight": weight(_current(psp), unit="pA", rel_std=0.1, **zero_bound(psp, bound_mode)),
                "delay": delay(delay_mean, rel_std=0.5, lower_bound=delay_min, bound_mode=bound_mode),
            }
        )
    return connections


def _poisson_background() -> dict[str, dict[str, Any]]:
    return {
        name: {
            "rate": background_rate,
            "indegree": background_indegree,
            "weight": weight(_current(psp_e), unit="pA"),
            "delay": delay(delay_e),
        }
        for name in sizes
    }


def generate_toy(*, config_dir: str | Path = "configs", network_name: str = "toy_from_builder") -> NetworkConfig:
    """Write ``<config_dir>/network/<network_name>/`` and check it."""

    neuron = {"model": neuron_model, "parameters": dict(neuron_parameters)}
    return write_network_directory(
        Path(config_dir) / "network" / network_name,
        populations=_populations(),
        neurons={"excitatory": neuron, "inhibitory": neuron},
        connections=_connections(),
        poisson_background=_poisson_background(),
        # No published rates for this toy.
        reference={},
        compact=False,
    )


def main(argv: list[str] | None = None) -> None:
    """Entry point of ``microcircuit-lab generate toy``."""
    parser = argparse.ArgumentParser(
        prog="microcircuit-lab generate toy",
        description="Write the toy network (the same as configs/network/toy) from Python.",
    )
    parser.add_argument("--config-dir", default="configs")
    parser.add_argument("--network-name", default="toy_from_builder")
    args = parser.parse_args(argv)

    generate_toy(config_dir=args.config_dir, network_name=args.network_name)
    print(f"Generated and validated {Path(args.config_dir) / 'network' / args.network_name}")


if __name__ == "__main__":
    main()
