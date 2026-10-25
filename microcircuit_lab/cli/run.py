"""
``microcircuit-lab run``: simulate a network and plot the results, or plot a
finished run again with ``--run-dir``.

The plots (raster, firing rates, ...) and their ``--<plot>`` flags come from
the plot registry. Plots of your own in the ``analyses/`` folder of your
project are included, so run the command from the project folder.
"""

import argparse
import logging
import sys
from typing import Any, get_args

import matplotlib.pyplot as plt

from microcircuit_lab import Simulation
from microcircuit_lab.analysis import (
    PLOT_REGISTRY,
    call_plot,
    check_reference_rates,
    check_unknown_plot_sections,
    discover_plots,
    list_areas,
    plot_enabled_in_config,
)
from microcircuit_lab.backends import BackendName
from microcircuit_lab.config.analysis import AnalysisConfig
from microcircuit_lab.run_folder import register_artifact


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="microcircuit-lab run",
        description="Simulate a network and plot it, or re-plot a finished run.",
    )
    parser.add_argument(
        "--config-dir",
        default="configs",
        help="Folder holding network/, simulation/ and analysis/ (default: configs).",
    )
    parser.add_argument(
        "--network", default=None, help="Name of the network to simulate: a folder in <config-dir>/network/."
    )
    parser.add_argument(
        "--simulation",
        default=None,
        help="Simulation settings to use: <config-dir>/simulation/<name>.yaml. Default: "
        "the network's name; if that file is missing, defaults are used, with a "
        "warning. A name given here must exist.",
    )
    parser.add_argument(
        "--run-dir",
        default=None,
        help="Re-plot a finished run (e.g. output/toy/<timestamp>) without "
        "simulating again. Use it instead of --network.",
    )
    parser.add_argument(
        "--backend",
        default=None,
        choices=get_args(BackendName),
        help="Simulator to run the network with. Overrides the simulation file's "
        "backend.name (default: nest).",
    )
    parser.add_argument(
        "--brian2-device",
        default=None,
        choices=["runtime", "cpp_standalone"],
        help="With Brian2: 'runtime' runs the network from Python (default), "
        "'cpp_standalone' compiles it to C++ and runs it with the simulation's threads. "
        "Overrides the simulation file's backend.options.",
    )
    parser.add_argument(
        "--brian2-codegen-target",
        default=None,
        choices=["auto", "cython", "numpy"],
        help="With Brian2 and the runtime device: 'auto' (Brian2's default) compiles "
        "the code with Cython, once per kind of network; 'numpy' compiles nothing and runs "
        "slower. Overrides the simulation file's backend.options.",
    )
    parser.add_argument(
        "--nest-modules",
        nargs="+",
        default=None,
        help="With NEST: compiled NEST modules (e.g. made by NESTML) to install before "
        "the network is built, for the models neurons.yaml and synapses.yaml name.",
    )
    parser.add_argument(
        "--model-modules",
        nargs="+",
        default=None,
        help="With Brian2: Python modules that define models, besides the files in "
        "models/brian2/.",
    )
    # Removed: split into --nest-modules and --model-modules.
    parser.add_argument("--extension-modules", nargs="+", default=None, help=argparse.SUPPRESS)
    parser.add_argument(
        "--analysis",
        default=None,
        help="Analysis settings to use: <config-dir>/analysis/<name>.yaml. Default: the "
        "network's name; if that file is missing, defaults are used, with a warning. "
        "A name given here must exist.",
    )
    parser.add_argument(
        "--begin", type=float, default=None,
        help="Analysis start time in ms. Overrides the analysis file.",
    )
    parser.add_argument(
        "--end", type=float, default=None,
        help="Analysis end time in ms. Overrides the analysis file.",
    )
    parser.add_argument(
        "--area",
        default=None,
        help="Area to plot for multi-area networks, or 'all' for one set of plots per "
        "area (plots/<area>/). Overrides the analysis file.",
    )
    parser.add_argument(
        "--reference",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Show the reference firing rates in the plots. Overrides the analysis file.",
    )
    for name in PLOT_REGISTRY:
        flag = name.replace("_", "-")
        parser.add_argument(
            f"--{flag}", action=argparse.BooleanOptionalAction, default=None,
            help=f"Make (or skip, with --no-{flag}) the {name} plot. Overrides the analysis file.",
        )
    parser.add_argument(
        "--validate-reference",
        action="store_true",
        help="Compare the simulated rates with the network's reference rates and print "
        "pass or fail. Does not change the exit code; skipped if the network has no "
        "reference rates.",
    )
    parser.add_argument(
        "--reference-rtol",
        type=float,
        default=0.5,
        help="Relative tolerance for --validate-reference.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Also open the plots in windows (they are always saved).",
    )

    args = parser.parse_args(argv)
    if args.extension_modules is not None:
        parser.error(
            "--extension-modules was split in two: --nest-modules for compiled NEST modules "
            "(e.g. from NESTML), --model-modules for Python modules with Brian2 models."
        )
    if bool(args.network) == bool(args.run_dir):
        parser.error("Pass exactly one of --network or --run-dir.")
    return args


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # Before parsing: the --<plot> flags are built from PLOT_REGISTRY.
    discover_plots()

    args = _parse_args(argv)

    if args.run_dir is not None:
        try:
            simulation = Simulation.from_run_dir(args.run_dir)
        except (FileNotFoundError, ValueError) as error:
            sys.exit(str(error))
        network_name = simulation.network_name
    else:
        backend_options: dict[str, Any] = {}
        if args.nest_modules:
            backend_options["nest_modules"] = args.nest_modules
        brian2_options = {
            "device": args.brian2_device,
            "codegen_target": args.brian2_codegen_target,
            "model_modules": args.model_modules,
        }
        brian2_options = {name: value for name, value in brian2_options.items() if value is not None}
        backend_options.update(brian2_options)
        try:
            simulation = Simulation.from_yaml(
                config_dir=args.config_dir,
                network_name=args.network,
                simulation_name=args.simulation,
                backend=args.backend,
                backend_options=backend_options,
            )
        except FileNotFoundError as error:
            sys.exit(str(error))
        if brian2_options and simulation.backend_name != "brian2":
            sys.exit(
                "--brian2-device, --brian2-codegen-target and --model-modules need the brian2 "
                f"backend (this run uses {simulation.backend_name}): pass --backend brian2 or set "
                "backend.name in the simulation file."
            )
        if args.nest_modules and simulation.backend_name != "nest":
            sys.exit(
                f"--nest-modules needs the nest backend (this run uses {simulation.backend_name})."
            )
        simulation.run()
        # With MPI, the first process alone plots.
        if not simulation.is_main_process:
            return
        network_name = args.network

    analysis_config = AnalysisConfig.from_yaml(
        config_dir=args.config_dir,
        network_name=network_name,
        analysis_name=args.analysis,
    )
    check_unknown_plot_sections(analysis_config)

    begin = args.begin if args.begin is not None else analysis_config.begin
    end = args.end if args.end is not None else analysis_config.end
    area = args.area if args.area is not None else analysis_config.area
    show_reference = (
        args.reference if args.reference is not None else analysis_config.show_reference
    )

    print(f"Run directory: {simulation.output_dir}")

    if area == "all":
        areas = list_areas(simulation)
        if not areas:
            raise SystemExit("--area all needs a multi-area network (<area>__<population> names).")
        plot_targets = [(a, simulation.output_dir / "plots" / a) for a in areas]
        area = None
    else:
        plot_targets = [(area, simulation.output_dir / "plots")]

    for name, spec in PLOT_REGISTRY.items():
        plot_config = analysis_config.plot_config(name, spec.config_cls)
        cli_override = getattr(args, name)
        enabled = (
            cli_override if cli_override is not None else plot_enabled_in_config(plot_config)
        )
        if not enabled:
            continue

        for plot_area, plots_dir in plot_targets:
            save_path = plots_dir / spec.filename
            save_path.parent.mkdir(parents=True, exist_ok=True)
            call_plot(
                spec, simulation,
                begin=begin, end=end, area=plot_area, style=analysis_config.style,
                config=plot_config, save_path=save_path, show=args.show,
                show_reference=show_reference,
            )
            register_artifact(simulation.output_dir, "plots", save_path)
            if not args.show:
                plt.close("all")

    print(f"Plots saved under: {simulation.output_dir / 'plots'}")
    print(
        "Re-plot without re-simulating: "
        f"microcircuit-lab run --run-dir {simulation.output_dir}"
    )

    if args.validate_reference:
        try:
            deviations = check_reference_rates(
                simulation, begin=begin, end=end, area=area,
                rtol=args.reference_rtol,
            )
            print(f"\nReference check passed (rtol={args.reference_rtol:.0%}):")
            for name, dev in deviations.items():
                print(f"  {name:>12}  {dev:+.1%}")
        except ValueError:
            print("\nNo reference.full_mean_rates on this network -- skipping --validate-reference.")
        except AssertionError as exc:
            print(f"\nReference check FAILED: {exc}")

