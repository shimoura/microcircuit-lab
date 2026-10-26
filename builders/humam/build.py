"""Generate simulation configs from HuMAM source data.

Sources:

* Pronold J, van Meegen A, Shimoura RO, Vollenbröker H, Senden M, Hilgetag CC,
  Bakker R, van Albada SJ (2024). Multi-scale spiking network model of human
  cerebral cortex. Cerebral Cortex. https://doi.org/10.1093/cercor/bhae409
* The HuMAM code, INM-6/human-multi-area-model, main at commit
  cab39b3: how the network is built (``src/simulation.py``) and the simulation
  defaults (``src/default_sim_params.py``).

``data/`` holds network data produced by the HuMAM code at full scale, with
cortico-cortical scaling 1.0 (E to E) and 2.0 (E to I); the parameters it was
produced with are in ``data/network_params.yaml``.
"""

from __future__ import annotations

import argparse
import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from microcircuit_lab.network.load import load_network
from microcircuit_lab.yaml_files import flow_records, read_yaml, write_yaml

LAYER_ALIAS = {
    "II/III": "L23",
    "IV": "L4",
    "V": "L5",
    "VI": "L6",
}

# HuMAM main (INM-6/human-multi-area-model @ cab39b3), src/default_sim_params.py:
# initial membrane potentials (mV), simulation resolution (ms) and the minimal
# cortico-cortical delay (ms; 0 means the resolution).
V0_MEAN = -150.0
V0_SD = 50.0
RESOLUTION = 0.1
DELAY_CC_MIN = 0.0

# HuMAM's delay distributions: drawn values below the minimum delay are clipped.
DELAY_DISTRIBUTIONS = {"lognormal_clipped": "lognormal", "normal_clipped": "normal"}


def _population_label(
    area: str,
    layer: str,
    pop: str,
    *,
    multi_area: bool,
) -> str:
    base = f"{LAYER_ALIAS.get(layer, layer)}_{pop}"
    if multi_area:
        return f"{area}__{base}"
    return base


@dataclass(frozen=True)
class HumamData:
    net_yaml: dict[str, Any]
    neuron_numbers: Any
    synapses_internal: Any
    weights: Any
    weights_sd: Any
    synapses_external: Any
    rate_ext: Any
    weights_ext: Any
    weights_ext_sd: Any
    delay_cc: Any
    delay_cc_sd: Any
    base_theory_rates: Any


def _load_pickle(path: Path) -> Any:
    with path.open("rb") as f:
        return pickle.load(f)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )


def _load_humam_data(
    data_dir: Path,
) -> HumamData:
    return HumamData(
        net_yaml=read_yaml(data_dir / "net.yaml"),
        neuron_numbers=_load_pickle(data_dir / "neuron_numbers.pkl"),
        synapses_internal=_load_pickle(data_dir / "synapses_internal.pkl"),
        weights=_load_pickle(data_dir / "weights.pkl"),
        weights_sd=_load_pickle(data_dir / "weights_sd.pkl"),
        synapses_external=_load_pickle(data_dir / "synapses_external.pkl"),
        rate_ext=_load_pickle(data_dir / "rate_ext.pkl"),
        weights_ext=_load_pickle(data_dir / "weights_ext.pkl"),
        weights_ext_sd=_load_pickle(data_dir / "weights_ext_sd.pkl"),
        delay_cc=_load_pickle(data_dir / "delay_cc.pkl"),
        delay_cc_sd=_load_pickle(data_dir / "delay_cc_sd.pkl"),
        base_theory_rates=_load_pickle(data_dir / "base_theory_rates.pkl"),
    )


def _resolve_selected_areas(
    area: str,
    area_list: list[str],
) -> tuple[list[str], bool]:
    if area.lower() == "all":
        selected_areas = list(area_list)
        return selected_areas, True

    if area not in area_list:
        raise ValueError(
            f"Unknown area '{area}'. "
            "Check names against HuMAM net.yaml area_list."
        )

    return [area], False


def _build_population_entries(
    *,
    selected_areas: list[str],
    layers: list[str],
    pops: list[str],
    neuron_numbers: Any,
    synapses_external: Any,
    multi_area: bool,
) -> tuple[list[tuple[tuple[str, str, str], str]], list[dict[str, Any]]]:
    labels: list[tuple[tuple[str, str, str], str]] = []
    population_entries: list[dict[str, Any]] = []

    for area_name in selected_areas:
        for layer in layers:
            for pop in pops:
                idx = (area_name, layer, pop)
                if idx not in neuron_numbers.index:
                    continue

                n = int(round(float(neuron_numbers.loc[idx])))
                if n <= 0:
                    continue

                label = _population_label(
                    area_name,
                    layer,
                    pop,
                    multi_area=multi_area,
                )
                labels.append((idx, label))

                k_ext = float(synapses_external.loc[idx]) / float(n)

                population_entries.append(
                    {
                        "name": label,
                        "size": n,
                        "neuron": pop,
                        "initial_state": {
                            "V_m": {"distribution": "normal", "mean": V0_MEAN, "std": V0_SD}
                        },
                        "background_indegree": k_ext,
                    }
                )

    return labels, population_entries


def _build_connections(
    *,
    labels: list[tuple[tuple[str, str, str], str]],
    synapses_internal: Any,
    weights: Any,
    weights_sd: Any,
    delay_cc: Any,
    delay_cc_sd: Any,
    delay_e: float,
    delay_i: float,
    delay_e_rel: float,
    delay_i_rel: float,
    delay_distribution: str,
) -> list[dict[str, Any]]:
    """Connections as HuMAM main makes them: PSC weights (pA) drawn from a normal
    and clipped at 0 keeping their sign, delays drawn from ``delay_distribution``
    and clipped at the minimum delay (the resolution locally, at least
    DELAY_CC_MIN between areas). A local connection gets the excitatory or
    inhibitory delay by the sign of its weight. Connections with weight 0 are
    skipped, as in HuMAM."""

    connections: list[dict[str, Any]] = []

    for src_idx, src_label in labels:
        for tgt_idx, tgt_label in labels:
            n_synapses = int(round(float(synapses_internal.loc[tgt_idx, src_idx])))
            if n_synapses <= 0:
                continue

            mean_psc = float(weights.loc[tgt_idx, src_idx])
            if mean_psc == 0.0:
                continue
            sd_psc = float(weights_sd.loc[tgt_idx, src_idx])

            source_is_excitatory = mean_psc > 0.0
            source_area = src_idx[0]
            target_area = tgt_idx[0]

            delay_mean = delay_e if source_is_excitatory else delay_i
            delay_rel = delay_e_rel if source_is_excitatory else delay_i_rel
            delay_min = RESOLUTION
            if source_area != target_area:
                cc_delay_mean = float(delay_cc.loc[target_area, source_area])
                if cc_delay_mean > 0.0:
                    delay_mean = cc_delay_mean
                    delay_rel = abs(float(delay_cc_sd.loc[target_area, source_area]) / cc_delay_mean)
                delay_min = max(DELAY_CC_MIN, RESOLUTION)

            connections.append(
                {
                    "source": src_label,
                    "target": tgt_label,
                    "n_synapses": n_synapses,
                    "weight": {
                        "mean": mean_psc,
                        "rel_std": abs(sd_psc / mean_psc),
                        "distribution": "normal",
                        "unit": "pA",
                    },
                    "delay": {
                        "mean": delay_mean,
                        "rel_std": delay_rel,
                        "distribution": DELAY_DISTRIBUTIONS[delay_distribution],
                        "minimum": delay_min,
                    },
                }
            )

    return connections


def _compute_missing_area_dc(
    *,
    labels: list[tuple[tuple[str, str, str], str]],
    area_list: list[str],
    layers: list[str],
    pops: list[str],
    selected_areas: list[str],
    neuron_numbers: Any,
    synapses_internal: Any,
    weights: Any,
    base_theory_rates: Any,
    neuron_params: dict[str, dict[str, float]],
) -> dict[str, float]:
    """
    DC current (pA) compensating each population in ``labels`` for the
    connections it would receive from areas outside ``selected_areas``,
    if the full multi-area network were simulated.

    Reuses network_compensation_current -- the same function that
    compensates for K_scaling downscaling -- with K_scaling=0.0. That
    factor normally expresses "what fraction of a connection's input
    survived scaling"; 0.0 means none of it survived (the source area
    isn't simulated at all), so the *entire* contribution is compensated
    rather than just the fraction lost to scaling.

    Each input is compensated with the target's ``tau_syn_ex`` or
    ``tau_syn_in``, by the sign of its weight (in HuMAM all inter-area
    connections are excitatory). ``neuron_params`` maps a population type
    (e.g. ``"E"``) to its neuron parameters.
    """

    other_areas = [a for a in area_list if a not in selected_areas]
    if not other_areas:
        return {}

    from microcircuit_lab.network.compensation import network_compensation_current

    compensation: dict[str, float] = {}

    for tgt_idx, tgt_label in labels:
        target_params = neuron_params[tgt_idx[2]]
        n_target = float(neuron_numbers.loc[tgt_idx])

        excitatory_input = 0.0
        inhibitory_input = 0.0
        for src_area in other_areas:
            for layer in layers:
                for pop in pops:
                    src_idx = (src_area, layer, pop)
                    if src_idx not in neuron_numbers.index:
                        continue
                    if src_idx not in base_theory_rates.index:
                        continue

                    n_synapses = float(synapses_internal.loc[tgt_idx, src_idx])
                    if n_synapses <= 0.0:
                        continue

                    mean_psc = float(weights.loc[tgt_idx, src_idx])
                    rate = float(base_theory_rates.loc[src_idx])

                    indegree = n_synapses / n_target
                    if mean_psc > 0.0:
                        excitatory_input += mean_psc * indegree * rate
                    else:
                        inhibitory_input += mean_psc * indegree * rate

        compensation[tgt_label] = float(
            network_compensation_current(
                network_input=excitatory_input,
                tau_syn=target_params["tau_syn_ex"],
                K_scaling=0.0,
            )
            + network_compensation_current(
                network_input=inhibitory_input,
                tau_syn=target_params["tau_syn_in"],
                K_scaling=0.0,
            )
        )

    return compensation


def _build_reference_rates(
    *,
    labels: list[tuple[tuple[str, str, str], str]],
    base_theory_rates: Any,
) -> dict[str, float]:
    """Map HuMAM full-scale theoretical rates to generated population names."""
    missing = [idx for idx, _ in labels if idx not in base_theory_rates.index]
    if missing:
        raise ValueError(
            "Missing HuMAM reference rates for populations: "
            f"{missing[:5]}" + (" ..." if len(missing) > 5 else "")
        )

    return {
        label: float(base_theory_rates.loc[idx])
        for idx, label in labels
    }


def _build_background_inputs(
    *,
    labels: list[tuple[tuple[str, str, str], str]],
    rate_ext: Any,
    weights_ext: Any,
    weights_ext_sd: Any,
) -> dict[str, dict[str, Any]]:
    """Poisson background as in HuMAM main: PSC weights (pA) drawn from a normal
    and clipped at 0, delay fixed at the resolution."""

    background_inputs: dict[str, dict[str, Any]] = {}

    for idx, label in labels:
        ext_mean_psc = float(weights_ext.loc[idx])
        ext_sd_psc = float(weights_ext_sd.loc[idx])

        background_inputs[label] = {
            "rate": float(rate_ext.loc[idx]),
            "weight": {
                "mean": ext_mean_psc,
                "rel_std": abs(ext_sd_psc / ext_mean_psc) if ext_mean_psc != 0.0 else 0.0,
                "distribution": "normal",
                "unit": "pA",
            },
            "delay": {
                "mean": RESOLUTION,
                "rel_std": 0.0,
                "distribution": "fixed",
            },
        }

    return background_inputs


def generate_humam_configs(
    *,
    area: str,
    config_dir: str | Path = "configs",
    network_name: str = "humam_single",
    simulation_name: str = "humam_single",
    data_dir: str | Path | None = None,
    n_scaling: float = 0.001,
    k_scaling: float = 0.001,
    t_sim: float = 500.0,
    rng_seed: int = 42,
    local_num_threads: int = 8,
    export_json: bool = False,
    compensate_missing_areas: bool = True,
) -> dict[str, Any]:
    """
    Generate HuMAM network configuration(s) from source data.

    If ``area == "all"``, a full multi-area network is generated.

    For a single area, ``compensate_missing_areas`` (default True) adds a
    per-population DC current compensating for the cortical input that
    area would normally receive from every other area, which is
    otherwise silently absent -- see _compute_missing_area_dc. Set to
    False to simulate the area genuinely isolated, with no such
    compensation; the returned/printed summary always states which mode
    was used, since the two are not interchangeable.

    Returns a dictionary containing key output paths.
    """

    try:
        import pandas as pd  # noqa: F401
    except ImportError as exc:  # pragma: no cover - runtime environment dependent
        raise RuntimeError(
            "pandas is required to load HuMAM pickle files. "
            "Install it in your active environment first."
        ) from exc

    package_data_dir = Path(__file__).parent / "data"
    resolved_data_dir = Path(data_dir) if data_dir is not None else package_data_dir
    data = _load_humam_data(resolved_data_dir)

    layers = data.net_yaml["layer_list"]
    pops = data.net_yaml["population_list"]
    selected_areas, multi_area = _resolve_selected_areas(
        area,
        data.net_yaml["area_list"],
    )

    # One neuron entry per population type, from net.yaml's neuron_params_<type>
    # and neuron_model_<type> (HuMAM: E and I).
    neuron_params = {pop: {**data.net_yaml[f"neuron_params_{pop}"], "I_e": 0.0} for pop in pops}
    neuron_models = {pop: data.net_yaml[f"neuron_model_{pop}"] for pop in pops}

    delay_e = float(data.net_yaml["delay_e"])
    delay_i = float(data.net_yaml["delay_i"])
    delay_e_rel = float(data.net_yaml["delay_e_sd"]) / delay_e
    delay_i_rel = float(data.net_yaml["delay_i_sd"]) / delay_i

    labels, population_entries = _build_population_entries(
        selected_areas=selected_areas,
        layers=layers,
        pops=pops,
        neuron_numbers=data.neuron_numbers,
        synapses_external=data.synapses_external,
        multi_area=multi_area,
    )

    if not population_entries:
        raise ValueError(
            f"No populations found for area '{area}'. "
            "Check the area name against HuMAM net.yaml area_list."
        )

    connections = _build_connections(
        labels=labels,
        synapses_internal=data.synapses_internal,
        weights=data.weights,
        weights_sd=data.weights_sd,
        delay_cc=data.delay_cc,
        delay_cc_sd=data.delay_cc_sd,
        delay_e=delay_e,
        delay_i=delay_i,
        delay_e_rel=delay_e_rel,
        delay_i_rel=delay_i_rel,
        delay_distribution=data.net_yaml["delay_distribution"],
    )

    background_inputs = _build_background_inputs(
        labels=labels,
        rate_ext=data.rate_ext,
        weights_ext=data.weights_ext,
        weights_ext_sd=data.weights_ext_sd,
    )

    missing_area_dc: dict[str, float] = {}
    if not multi_area and compensate_missing_areas:
        missing_area_dc = _compute_missing_area_dc(
            labels=labels,
            area_list=data.net_yaml["area_list"],
            layers=layers,
            pops=pops,
            selected_areas=selected_areas,
            neuron_numbers=data.neuron_numbers,
            synapses_internal=data.synapses_internal,
            weights=data.weights,
            base_theory_rates=data.base_theory_rates,
            neuron_params=neuron_params,
        )

    scaling = {
        "N_scaling": n_scaling,
        "K_scaling": k_scaling,
        "preserve_mean_input": True,
        "preserve_variance": True,
        "compensate_recurrent_input": False,
    }

    reference = {
        "full_mean_rates": _build_reference_rates(
            labels=labels,
            base_theory_rates=data.base_theory_rates,
        ),
    }

    network_manifest = {
        "populations": "populations.yaml",
        "neurons": "neurons.yaml",
        "connectivity": "connectivity.yaml",
        "background_inputs": "background_inputs.yaml",
        "scaling": "scaling.yaml",
        "reference": "reference.yaml",
    }

    if missing_area_dc:
        # One neuron definition per population instead of two shared ones,
        # since each population needs its own compensation current baked
        # into I_e. Nothing in the schema requires sharing -- populations
        # already reference their neuron by name.
        neurons = {
            "neurons": {
                label: {
                    "model": neuron_models[idx[2]],
                    "parameters": {
                        **neuron_params[idx[2]],
                        "I_e": missing_area_dc.get(label, 0.0),
                    },
                }
                for idx, label in labels
            }
        }
        for entry in population_entries:
            entry["neuron"] = entry["name"]
    else:
        neurons = {
            "neurons": {
                pop: {"model": neuron_models[pop], "parameters": neuron_params[pop]}
                for pop in pops
            }
        }

    simulation_cfg = {
        "t_sim": t_sim,
        "resolution": RESOLUTION,
        "rng_seed": rng_seed,
        "local_num_threads": local_num_threads,
        "print_time": False,
        "recording": {
            "spike_recording": True,
            "voltage_recording": False,
            "voltage_interval": 1.0,
        },
        "output": {
            "output_dir": f"output/{simulation_name}",
            "overwrite": False,
            "save_metadata": True,
            "save_config": True,
        },
    }

    config_root = Path(config_dir)
    network_dir = config_root / "network" / network_name
    simulation_path = config_root / "simulation" / f"{simulation_name}.yaml"
    network_dir.mkdir(parents=True, exist_ok=True)
    simulation_path.parent.mkdir(parents=True, exist_ok=True)

    yaml_payloads = {
        "network.yaml": network_manifest,
        "populations.yaml": {"populations": population_entries},
        "neurons.yaml": neurons,
        "connectivity.yaml": {"bound_mode": "clip", "connections": connections},
        "background_inputs.yaml": {"background_inputs": background_inputs},
        "scaling.yaml": scaling,
        "reference.yaml": reference,
    }

    # State missing-area compensation directly in neurons.yaml -- where it
    # actually shows up (I_e) -- so it's clear to anyone reading the
    # generated config later, not just at generation time.
    other_area_count = len(data.net_yaml["area_list"]) - len(selected_areas)
    neurons_header: str | None = None
    if not multi_area and other_area_count > 0:
        if missing_area_dc:
            values = list(missing_area_dc.values())
            neurons_header = (
                f"Compensated for {other_area_count} area(s) not simulated: each "
                "population's I_e includes a DC current for the cortical input it "
                "would otherwise be missing (see humam.build._compute_missing_area_dc).\n"
                f"I_e compensation range: {min(values):.3f} to {max(values):.3f} pA.\n"
                "Regenerate with --no-compensate-missing-areas for a genuinely "
                "isolated area instead (no compensation)."
            )
        else:
            neurons_header = (
                f"WARNING: this area is simulated in isolation from the other "
                f"{other_area_count} area(s) of the full HuMAM model, with NO "
                "compensation for the cortical input it would normally receive from "
                "them -- I_e is not adjusted. Regenerate without "
                "--no-compensate-missing-areas to add that compensation."
            )

    # Large uniform tables (thousands of rows for multi-area networks) are
    # written one-record-per-line instead of full YAML block style.
    flow_style_fields = {
        "populations.yaml": "populations",
        "connectivity.yaml": "connections",
        "background_inputs.yaml": "background_inputs",
    }
    for name, payload in yaml_payloads.items():
        field = flow_style_fields.get(name)
        if field is not None:
            payload = {**payload, field: flow_records(payload[field])}
        header = neurons_header if name == "neurons.yaml" else None
        write_yaml(network_dir / name, payload, header_comment=header)

    write_yaml(simulation_path, simulation_cfg)

    if export_json:
        for name, payload in yaml_payloads.items():
            _write_json(network_dir / name.replace(".yaml", ".json"), payload)
        _write_json(
            simulation_path.with_suffix(".json"),
            simulation_cfg,
        )

    return {
        "network_dir": network_dir,
        "simulation_path": simulation_path,
        "missing_area_compensation_applied": bool(missing_area_dc),
        "other_area_count": other_area_count,
    }


def _add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--area",
        default="rostralanteriorcingulate",
        help="HuMAM area, or 'all' for the multi-area network (default: the area of the bundled humam_single).",
    )
    parser.add_argument("--config-dir", default="configs")
    parser.add_argument("--network-name", default=None)
    parser.add_argument("--simulation-name", default=None)
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--n-scaling", type=float, default=0.001)
    parser.add_argument("--k-scaling", type=float, default=0.001)
    parser.add_argument("--t-sim", type=float, default=500.0)
    parser.add_argument("--rng-seed", type=int, default=42)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--export-json", action="store_true")
    parser.add_argument(
        "--no-compensate-missing-areas",
        dest="compensate_missing_areas",
        action="store_false",
        help="For a single-area network, do NOT compensate for the cortical input "
        "the area would normally receive from the rest of HuMAM (default: compensate).",
    )


def main(argv: list[str] | None = None) -> None:
    """Entry point. ``microcircuit-lab generate`` discovers this function (via
    ``builders.humam.main``) and forwards it the
    arguments after the model name.
    """
    parser = argparse.ArgumentParser(
        prog="microcircuit-lab generate humam",
        description=(
            "Generate HuMAM configs from source data. "
            "Use --area all for a full multi-area network."
        ),
    )
    _add_arguments(parser)
    _run(parser.parse_args(argv))


def _run(args: argparse.Namespace) -> None:
    default_name = "humam_all" if args.area.lower() == "all" else "humam_single"
    network_name = args.network_name or default_name
    simulation_name = args.simulation_name or default_name

    paths = generate_humam_configs(
        area=args.area,
        config_dir=args.config_dir,
        network_name=network_name,
        simulation_name=simulation_name,
        data_dir=args.data_dir,
        n_scaling=args.n_scaling,
        k_scaling=args.k_scaling,
        t_sim=args.t_sim,
        rng_seed=args.rng_seed,
        local_num_threads=args.threads,
        export_json=args.export_json,
        compensate_missing_areas=args.compensate_missing_areas,
    )
    print(f"Generated network config in: {paths['network_dir']}")
    print(f"Generated simulation config: {paths['simulation_path']}")

    load_network(paths["network_dir"])
    print("Validated: config is a usable input to the simulation pipeline.")

    if paths.get("other_area_count", 0) > 0:
        if paths["missing_area_compensation_applied"]:
            print(
                f"\nCompensated for {paths['other_area_count']} area(s) not simulated "
                "(see neurons.yaml). Use --no-compensate-missing-areas to disable."
            )
        else:
            print(
                f"\nWARNING: area simulated in isolation from {paths['other_area_count']} "
                "other area(s), with NO compensation for their normal cortical input "
                "(see neurons.yaml). Omit --no-compensate-missing-areas to enable it."
            )

    print("\nRun with:")
    print(
        "microcircuit-lab run "
        f"--config-dir {args.config_dir} "
        f"--network {network_name} "
        f"--simulation {simulation_name}"
    )


if __name__ == "__main__":
    main()
