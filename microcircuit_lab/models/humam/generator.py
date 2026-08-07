"""Generate simulation configs from HuMAM source data."""

from __future__ import annotations

import argparse
import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from microcircuit_lab.network.synapses import psp_to_psc_iaf_psc_exp
from microcircuit_lab.io.files import read_yaml


LAYER_ALIAS = {
    "II/III": "L23",
    "IV": "L4",
    "V": "L5",
    "VI": "L6",
}


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


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(data, sort_keys=False),
        encoding="utf-8",
    )


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )


def _psc_to_psp(
    psc: float,
    target_params: dict[str, float],
    is_inhibitory: bool,
) -> float:
    tau_syn = (
        target_params["tau_syn_in"] if is_inhibitory else target_params["tau_syn_ex"]
    )
    psc_per_psp = psp_to_psc_iaf_psc_exp(
        psp=1.0,
        C_m=target_params["C_m"],
        tau_m=target_params["tau_m"],
        tau_syn=tau_syn,
    )
    return psc / psc_per_psp


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
                        "neuron": "excitatory" if pop == "E" else "inhibitory",
                        "V0_mean": -65.0,
                        "V0_std": 5.0,
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
    excitatory_params: dict[str, float],
    inhibitory_params: dict[str, float],
    delay_e: float,
    delay_i: float,
    delay_e_rel: float,
    delay_i_rel: float,
) -> list[dict[str, Any]]:
    connections: list[dict[str, Any]] = []

    for src_idx, src_label in labels:
        for tgt_idx, tgt_label in labels:
            n_synapses = int(round(float(synapses_internal.loc[tgt_idx, src_idx])))
            if n_synapses <= 0:
                continue

            mean_psc = float(weights.loc[tgt_idx, src_idx])
            sd_psc = float(weights_sd.loc[tgt_idx, src_idx])

            target_is_inhibitory = tgt_idx[2] == "I"
            target_params = inhibitory_params if target_is_inhibitory else excitatory_params

            mean_psp = _psc_to_psp(
                psc=mean_psc,
                target_params=target_params,
                is_inhibitory=(mean_psc < 0.0),
            )

            rel_std = abs(sd_psc / mean_psc) if mean_psc != 0.0 else 0.0

            source_is_excitatory = src_idx[2] == "E"
            source_area = src_idx[0]
            target_area = tgt_idx[0]

            if source_area != target_area:
                cc_delay_mean = float(delay_cc.loc[target_area, source_area])
                cc_delay_sd = float(delay_cc_sd.loc[target_area, source_area])
                if cc_delay_mean > 0.0:
                    delay_mean = cc_delay_mean
                    delay_rel = abs(cc_delay_sd / cc_delay_mean)
                else:
                    delay_mean = delay_e if source_is_excitatory else delay_i
                    delay_rel = delay_e_rel if source_is_excitatory else delay_i_rel
            else:
                delay_mean = delay_e if source_is_excitatory else delay_i
                delay_rel = delay_e_rel if source_is_excitatory else delay_i_rel

            connections.append(
                {
                    "source": src_label,
                    "target": tgt_label,
                    "n_synapses": n_synapses,
                    "weight": {
                        "mean": mean_psp,
                        "rel_std": rel_std,
                        "distribution": "normal",
                        "unit": "PSP",
                    },
                    "delay": {
                        "mean": delay_mean,
                        "rel_std": delay_rel,
                        "distribution": "lognormal",
                    },
                }
            )

    return connections


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


def _build_inputs(
    *,
    labels: list[tuple[tuple[str, str, str], str]],
    rate_ext: Any,
    weights_ext: Any,
    weights_ext_sd: Any,
    excitatory_params: dict[str, float],
    inhibitory_params: dict[str, float],
    resolution: float,
) -> dict[str, dict[str, Any]]:
    inputs: dict[str, dict[str, Any]] = {}

    for idx, label in labels:
        pop = idx[2]
        target_is_inhibitory = pop == "I"
        target_params = inhibitory_params if target_is_inhibitory else excitatory_params

        ext_mean_psc = float(weights_ext.loc[idx])
        ext_sd_psc = float(weights_ext_sd.loc[idx])

        ext_mean_psp = _psc_to_psp(
            psc=ext_mean_psc,
            target_params=target_params,
            is_inhibitory=False,
        )

        ext_rel_std = abs(ext_sd_psc / ext_mean_psc) if ext_mean_psc != 0.0 else 0.0

        inputs[label] = {
            "rate": float(rate_ext.loc[idx]),
            "weight": {
                "mean": ext_mean_psp,
                "rel_std": ext_rel_std,
                "distribution": "normal",
                "unit": "PSP",
            },
            "delay": {
                "mean": resolution,
                "rel_std": 0.0,
                "distribution": "fixed",
            },
        }

    return inputs


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
) -> dict[str, Path]:
    """
    Generate HuMAM network configuration(s) from source data.

    If ``area == "all"``, a full multi-area network is generated.

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

    excitatory_params = {
        **data.net_yaml["neuron_params_E"],
        "I_e": 0.0,
    }
    inhibitory_params = {
        **data.net_yaml["neuron_params_I"],
        "I_e": 0.0,
    }

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
        excitatory_params=excitatory_params,
        inhibitory_params=inhibitory_params,
        delay_e=delay_e,
        delay_i=delay_i,
        delay_e_rel=delay_e_rel,
        delay_i_rel=delay_i_rel,
    )

    inputs = _build_inputs(
        labels=labels,
        rate_ext=data.rate_ext,
        weights_ext=data.weights_ext,
        weights_ext_sd=data.weights_ext_sd,
        excitatory_params=excitatory_params,
        inhibitory_params=inhibitory_params,
        resolution=0.1
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
        "inputs": "inputs.yaml",
        "scaling": "scaling.yaml",
        "reference": "reference.yaml",
    }

    neurons = {
        "neurons": {
            "excitatory": {
                "model": data.net_yaml["neuron_model_E"],
                "parameters": excitatory_params,
            },
            "inhibitory": {
                "model": data.net_yaml["neuron_model_I"],
                "parameters": inhibitory_params,
            },
        }
    }

    simulation_cfg = {
        "t_sim": t_sim,
        "resolution": 0.1,
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
        "connectivity.yaml": {"connections": connections},
        "inputs.yaml": {"inputs": inputs},
        "scaling.yaml": scaling,
        "reference.yaml": reference,
    }

    for name, payload in yaml_payloads.items():
        _write_yaml(network_dir / name, payload)

    _write_yaml(simulation_path, simulation_cfg)

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
    }



def generate_single_area_configs(**kwargs: Any) -> dict[str, Path]:
    """Backward-compatible alias for :func:`generate_humam_configs`."""

    return generate_humam_configs(**kwargs)

def _add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--area", default="bankssts")
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


def add_cli(subparser: argparse.ArgumentParser) -> None:
    """Register HuMAM generation arguments on a ``scripts/generate.py`` subparser."""

    _add_arguments(subparser)
    subparser.set_defaults(func=_run)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate HuMAM configs from source data. "
            "Use --area all for a full multi-area network."
        ),
    )
    _add_arguments(parser)
    args = parser.parse_args()
    _run(args)


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
    )
    print(f"Generated network config in: {paths['network_dir']}")
    print(f"Generated simulation config: {paths['simulation_path']}")
    print("\nRun with:")
    print(
        "python scripts/run_simulation.py "
        f"--config-dir {args.config_dir} "
        f"--network {network_name} "
        f"--simulation {simulation_name}"
    )


if __name__ == "__main__":
    main()
