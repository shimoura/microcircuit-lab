"""Run any pre-generated network configuration and optional diagnostics."""

import argparse
import logging

from microcircuit_lab import Simulation
from microcircuit_lab.analysis import (
    POWER_SPECTRUM_METHODS,
    FiringRatePlotConfig,
    PlotStyle,
    PowerSpectrumPlotConfig,
    RasterPlotConfig,
    check_reference_rates,
    plot_firing_rates,
    plot_isi_cv,
    plot_power_spectrum,
    plot_raster,
)
from microcircuit_lab.io.output import register_artifact

PLOT_STYLE = PlotStyle(
    color_mode="layer",
    cell_type_colors={"E": "#595289", "I": "#af143c"},
    population_labels={"L23_E": "L2/3_E", "L23_I": "L2/3_I"},
    tick_label_size=5.0,
    axis_label_size=8.0,
    legend_size=6.0,
    dpi=300,
)

RASTER_CONFIG = RasterPlotConfig(
    marker_size=1.0,
    alpha=1.0,
    figsize=(4, 3),
    separator_lines=True,
    show_legend=False,
)

FIRING_RATE_CONFIG = FiringRatePlotConfig(
    figsize=(5, 3.5),
    show_points=False,
    show_mean=True,
    show_legend=True,
)

POWER_SPECTRUM_CONFIG = PowerSpectrumPlotConfig(
    width_per_column=3.0,
    height_per_row=1.6,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a generated network configuration.")
    parser.add_argument("--config-dir", default="configs")
    parser.add_argument("--network", default="pd14", help="Network config directory name.")
    parser.add_argument("--simulation", default="default", help="Simulation config name.")
    parser.add_argument("--area", default=None, help="Area to plot for multi-area networks.")
    parser.add_argument("--begin", type=float, default=0.0, help="Analysis start time in ms.")
    parser.add_argument("--end", type=float, default=None, help="Analysis end time in ms.")
    parser.add_argument("--reference", action="store_true", help="Show reference firing rates.")
    parser.add_argument("--no-raster", action="store_true")
    parser.add_argument("--no-firing-rates", action="store_true")
    parser.add_argument("--no-power-spectrum", action="store_true")
    parser.add_argument("--no-isi-cv", action="store_true")
    parser.add_argument(
        "--power-spectrum-method",
        default="welch",
        choices=sorted(POWER_SPECTRUM_METHODS),
        help="Spectral estimator for the power-spectrum plot.",
    )
    parser.add_argument(
        "--validate-reference",
        action="store_true",
        help="Check simulated rates against reference.full_mean_rates and print pass/fail "
        "(non-fatal; does not affect exit code). No-op if the network has no reference.",
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
        help="Open plot windows interactively (plots are always saved to output_dir regardless).",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    args = _parse_args()
    simulation = Simulation.from_yaml(
        config_dir=args.config_dir,
        network_name=args.network,
        simulation_name=args.simulation,
    )
    simulation.run()

    plots_dir = simulation.output_dir / "plots"

    if not args.no_raster:
        raster_path = plots_dir / "raster.png"
        plot_raster(
            simulation,
            begin=args.begin,
            end=args.end,
            area=args.area,
            max_neurons_per_population=None,
            style=PLOT_STYLE,
            config=RASTER_CONFIG,
            save_path=raster_path,
            show=args.show,
        )
        register_artifact(simulation.output_dir, "plots", raster_path)

    if not args.no_firing_rates:
        firing_rates_path = plots_dir / "firing_rates.png"
        plot_firing_rates(
            simulation,
            begin=args.begin,
            end=args.end,
            area=args.area,
            show_reference=args.reference,
            style=PLOT_STYLE,
            config=FIRING_RATE_CONFIG,
            save_path=firing_rates_path,
            show=args.show,
        )
        register_artifact(simulation.output_dir, "plots", firing_rates_path)

    if not args.no_power_spectrum:
        power_spectrum_path = plots_dir / "power_spectrum.png"
        plot_power_spectrum(
            simulation,
            begin=args.begin,
            end=args.end,
            area=args.area,
            method=args.power_spectrum_method,
            style=PLOT_STYLE,
            config=POWER_SPECTRUM_CONFIG,
            save_path=power_spectrum_path,
            show=args.show,
        )
        register_artifact(simulation.output_dir, "plots", power_spectrum_path)

    if not args.no_isi_cv:
        isi_cv_path = plots_dir / "isi_cv.png"
        plot_isi_cv(
            simulation,
            begin=args.begin,
            end=args.end,
            area=args.area,
            style=PLOT_STYLE,
            config=FIRING_RATE_CONFIG,
            save_path=isi_cv_path,
            show=args.show,
        )
        register_artifact(simulation.output_dir, "plots", isi_cv_path)

    if args.validate_reference:
        try:
            deviations = check_reference_rates(
                simulation, begin=args.begin, end=args.end, area=args.area,
                rtol=args.reference_rtol,
            )
            print(f"\nReference check passed (rtol={args.reference_rtol:.0%}):")
            for name, dev in deviations.items():
                print(f"  {name:>12}  {dev:+.1%}")
        except ValueError:
            print("\nNo reference.full_mean_rates on this network -- skipping --validate-reference.")
        except AssertionError as exc:
            print(f"\nReference check FAILED: {exc}")


if __name__ == "__main__":
    main()
