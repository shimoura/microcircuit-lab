"""High-level HuMAM configuration and simulation workflow."""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path

from microcircuit_lab.importers.humam import generate_humam_configs
from microcircuit_lab.simulation.runner import Simulation
from microcircuit_lab.analysis import RasterPlotConfig, plot_raster


logger = logging.getLogger(__name__)


@dataclass
class HumamRunConfig:
    """Scientist-facing HuMAM run settings."""

    area: str = "bankssts"
    config_dir: str | Path = "configs"
    network_name: str = "humam_single"
    simulation_name: str = "humam_single"
    data_dir: str | Path | None = None
    n_scaling: float = 0.001
    k_scaling: float = 0.001
    t_sim: float = 500.0
    rng_seed: int = 42
    threads: int = 8
    export_json: bool = False
    skip_generate: bool = False
    raster_area: str | None = None
    raster_style: RasterPlotConfig | None = None


def normalize_config(config: HumamRunConfig) -> HumamRunConfig:
    """Return a normalized run config with consistent defaults."""

    normalized = HumamRunConfig(**vars(config))

    if normalized.area.lower() == "all":
        if normalized.network_name == "humam_single":
            normalized.network_name = "humam_all"
        if normalized.simulation_name == "humam_single":
            normalized.simulation_name = "humam_all"

    return normalized


def run_humam(config: HumamRunConfig) -> Simulation:
    """Generate (optional) and run a HuMAM simulation from a typed config."""

    config = normalize_config(config)

    config_dir = Path(config.config_dir)
    network_dir = config_dir / "network" / config.network_name
    simulation_path = config_dir / "simulation" / f"{config.simulation_name}.yaml"

    if not config.skip_generate:
        paths = generate_humam_configs(
            area=config.area,
            config_dir=config_dir,
            network_name=config.network_name,
            simulation_name=config.simulation_name,
            data_dir=config.data_dir,
            n_scaling=config.n_scaling,
            k_scaling=config.k_scaling,
            t_sim=config.t_sim,
            rng_seed=config.rng_seed,
            local_num_threads=config.threads,
            export_json=config.export_json,
        )
        logger.info("Generated network config in %s", paths["network_dir"])
        logger.info("Generated simulation config at %s", paths["simulation_path"])
    elif not network_dir.exists() or not simulation_path.exists():
        raise FileNotFoundError(
            "Missing pre-generated config files. "
            "Run with generation enabled first."
        )

    simulation = Simulation.from_yaml(
        config_dir=config_dir,
        network_name=config.network_name,
        simulation_name=config.simulation_name,
    )
    simulation.run()

    if config.raster_area is not None:
        plot_raster(simulation, area=config.raster_area, style=config.raster_style)

    return simulation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate and run HuMAM simulation. "
            "Use --area all for the multi-area model."
        ),
    )
    parser.add_argument("--area", default="bankssts")
    parser.add_argument("--config-dir", default="configs")
    parser.add_argument("--network-name", default="humam_single")
    parser.add_argument("--simulation-name", default="humam_single")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--n-scaling", type=float, default=0.001)
    parser.add_argument("--k-scaling", type=float, default=0.001)
    parser.add_argument("--t-sim", type=float, default=500.0)
    parser.add_argument("--rng-seed", type=int, default=42)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--export-json", action="store_true")
    parser.add_argument("--raster-area", default=None)
    parser.add_argument(
        "--skip-generate",
        action="store_true",
        help="Use existing configs without regenerating from HuMAM data.",
    )
    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> HumamRunConfig:
    """Convert CLI arguments into typed run config."""

    return HumamRunConfig(
        area=args.area,
        config_dir=args.config_dir,
        network_name=args.network_name,
        simulation_name=args.simulation_name,
        data_dir=args.data_dir,
        n_scaling=args.n_scaling,
        k_scaling=args.k_scaling,
        t_sim=args.t_sim,
        rng_seed=args.rng_seed,
        threads=args.threads,
        export_json=args.export_json,
        skip_generate=args.skip_generate,
        raster_area=args.raster_area,
    )


def run_humam_simulation(args: argparse.Namespace) -> None:
    """Backward-compatible wrapper used by existing callers."""

    run_humam(config_from_args(args))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run_humam_simulation(parse_args())


if __name__ == "__main__":
    main()
