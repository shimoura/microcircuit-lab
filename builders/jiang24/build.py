"""Generate the Jiang et al. (2024) network configuration from ``data.py``.

Writes ``configs/network/jiang24/``: the publication's Base model, with static
synapses. It has 13 populations (E, PV and SOM cells in L2/3, L4, L5 and L6, and
VIP cells in L2/3), neuron parameters per cell type, connections made pair by
pair with a probability per projection, lognormal weights and delays, and one
Poisson background train per neuron. The weights are given as PSPs (mV) and
written as the currents (pA) that give them with each target's neuron.

With ``stp=True`` (``--stp``), writes ``configs/network/jiang24_stp/`` instead:
the publication's Base-STP model, the Base model with three changes (the last
section of ``data.py``):

* the projections with short-term plasticity use NEST's ``tsodyks_synapse``, one
  entry of ``synapses.yaml`` per set of parameters, named ``stp_<source>_to_<target>``
  after its key in ``data.stp``;
* the mean PSPs of those projections are multiplied by their weight factors;
* the background rates are the ones fitted for this model.

Also writes ``configs/simulation/<name>.yaml``, with the publication's duration
and time step, on which the delays depend; ``configs/analysis/<name>.yaml``, with
the publication's colors for the bundled plots; and
``configs/analysis/<name>_fig6.yaml``, which also switches on the plots of Fig. 6A
(Base) or 6B (Base-STP) (``analyses/jiang24_*.py``). ``<name>`` is ``jiang24``
or ``jiang24_stp``.
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


def _cell_type(name: str) -> str:
    """The cell type of a population, or of a key of ``data.stp`` (a population or a cell type)."""
    return name.split("_")[-1]


def _current(psp: float, neuron: str) -> float:
    """The current amplitude (pA) of a PSP amplitude (mV) onto the neuron entry
    ``neuron``. Excitation uses tau_syn_ex, inhibition tau_syn_in."""
    return psp_to_psc_iaf_psc_exp(
        psp,
        C_m=data.neurons[neuron]["C_m"],
        tau_m=data.neurons[neuron]["tau_m"],
        tau_syn=data.tau_syn_ex if psp > 0 else data.tau_syn_in,
    )


def _synapse_name(key: tuple[str, str]) -> str:
    return f"stp_{key[0]}_to_{key[1]}"


def _stp_key(source: str, target: str) -> tuple[str, str] | None:
    """The key of ``data.stp`` for the projection from the population ``source``
    onto ``target``: the populations themselves if listed, else their cell types;
    None for a static projection."""
    for key in ((source, target), (_cell_type(source), _cell_type(target))):
        if key in data.stp:
            return key
    return None


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


def _build_synapses() -> dict[str, dict[str, Any]]:
    """Base-STP only: one entry per set of STP parameters. tau_psc, the decay
    time of the synapse's current, is the time constant of its source's input,
    as in the original code (Network.assign_stp)."""
    return {
        _synapse_name(key): {
            "model": data.synapse_model,
            "parameters": {
                **parameters,
                "tau_psc": data.tau_syn_ex if _cell_type(key[0]) == "E" else data.tau_syn_in,
            },
        }
        for key, parameters in data.stp.items()
    }


def _build_connections(stp: bool) -> list[dict[str, Any]]:
    """With ``stp``, the projections with STP get their synapse and weight factor."""
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

            connection = {
                "source": source,
                "target": target,
                "rule": "pairwise_bernoulli",
                "p": probability,
            }
            if stp:
                key = _stp_key(source, target)
                if key is not None:
                    connection["synapse"] = _synapse_name(key)
                psp = data.weight_factors[target_index][source_index] * psp
            connection["weight"] = weight(
                _current(psp, target_neuron),
                unit="pA",
                rel_std=data.weight_rel_std,
                distribution="lognormal",
            )
            connection["delay"] = delay(
                delay_mean,
                rel_std=delay_std / delay_mean,
                distribution="lognormal",
                lower_bound=data.delay_min,
                bound_mode="redraw",
            )
            connections.append(connection)

    return connections


def _build_poisson_background(stp: bool) -> dict[str, dict[str, Any]]:
    rates = data.bg_rate_stp if stp else data.bg_rate
    return {
        name: {
            "rate": rates[_cell_type(name)],
            "indegree": data.bg_indegree,
            "weight": weight(_current(data.bg_psp, neuron), unit="pA"),
            "delay": delay(data.bg_delay),
        }
        for name, _, neuron in data.populations
    }


def generate_jiang24(
    *,
    config_dir: str | Path = "configs",
    network_name: str | None = None,
    stp: bool = False,
) -> NetworkConfig:
    """Write ``<config_dir>/network/<network_name>/``, validate it, and write
    ``<network_name>.yaml`` in ``<config_dir>/simulation/`` and ``<config_dir>/analysis/``,
    and ``<network_name>_fig6.yaml`` in ``<config_dir>/analysis/``.

    The Base model, or with ``stp`` the Base-STP model. ``network_name`` defaults
    to ``jiang24``, or ``jiang24_stp`` with ``stp``."""

    if network_name is None:
        network_name = "jiang24_stp" if stp else "jiang24"
    style = {"color_mode": "cell_type", "cell_type_colors": data.cell_type_colors}
    write_yaml(
        Path(config_dir) / "simulation" / f"{network_name}.yaml",
        {
            "t_sim": data.t_sim,
            "resolution": data.resolution,
            "rng_seed": data.rng_seed,
            "local_num_threads": data.local_num_threads,
        },
    )
    write_yaml(Path(config_dir) / "analysis" / f"{network_name}.yaml", {"style": style})
    write_yaml(
        Path(config_dir) / "analysis" / f"{network_name}_fig6.yaml",
        {
            "style": style,
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
        connections=_build_connections(stp),
        poisson_background=_build_poisson_background(stp),
        synapses=_build_synapses() if stp else None,
        reference=data.full_mean_rates_stp if stp else data.full_mean_rates,
        compact=False,
    )


def main(argv: list[str] | None = None) -> None:
    """Entry point of ``microcircuit-lab generate jiang24``."""
    parser = argparse.ArgumentParser(
        prog="microcircuit-lab generate jiang24",
        description=(
            "Generate the Jiang et al. (2024) network configuration from its published parameters: "
            "the Base model, or with --stp the Base-STP model."
        ),
    )
    parser.add_argument("--config-dir", default="configs")
    parser.add_argument("--network-name", default=None, help="default: jiang24, or jiang24_stp with --stp")
    parser.add_argument(
        "--stp",
        action="store_true",
        help="write jiang24_stp instead: the Base-STP model, with short-term plasticity on most "
        "projections (NEST's tsodyks_synapse, so NEST only), their weights scaled, and its own "
        "background rates",
    )
    args = parser.parse_args(argv)

    name = args.network_name or ("jiang24_stp" if args.stp else "jiang24")
    generate_jiang24(config_dir=args.config_dir, network_name=name, stp=args.stp)
    print(f"Generated and validated {Path(args.config_dir) / 'network' / name}")
    print(f"Generated {Path(args.config_dir) / 'simulation' / name}.yaml")
    print(f"Generated {Path(args.config_dir) / 'analysis' / name}.yaml")
    print(f"Generated {Path(args.config_dir) / 'analysis' / name}_fig6.yaml")


if __name__ == "__main__":
    main()
