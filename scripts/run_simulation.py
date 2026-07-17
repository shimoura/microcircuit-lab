"""Run any pre-generated network configuration and optional diagnostics."""

import argparse

from microcircuit_lab import Simulation
from microcircuit_lab.analysis import (
    FiringRatePlotConfig,
    PlotStyle,
    RasterPlotConfig,
    plot_firing_rates,
    plot_raster,
)

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
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    simulation = Simulation.from_yaml(
        config_dir=args.config_dir,
        network_name=args.network,
        simulation_name=args.simulation,
    )
    simulation.run()

    if not args.no_raster:
        plot_raster(
            simulation,
            begin=args.begin,
            end=args.end,
            area=args.area,
            max_neurons_per_population=None,
            style=PLOT_STYLE,
            config=RASTER_CONFIG,
        )

    if not args.no_firing_rates:
        plot_firing_rates(
            simulation,
            begin=args.begin,
            end=args.end,
            area=args.area,
            show_reference=args.reference,
            style=PLOT_STYLE,
            config=FIRING_RATE_CONFIG,
        )


if __name__ == "__main__":
    main()
