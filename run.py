"""Run any pre-generated network configuration and optionally plot spikes."""

from microcircuit_lab.analysis import RasterPlotConfig, plot_raster
from microcircuit_lab.simulation.runner import Simulation

NETWORK_NAME = "pd14"
SIMULATION_NAME = "default"

RASTER_AREA = None
RASTER_BEGIN = 500.0  # ms
RASTER_END = 1500.0  # ms

RASTER_STYLE = RasterPlotConfig(
    color_mode="cell_type",
    cell_type_colors={
        "E": "#595289",
        "I": "#af143c",
    },
    population_labels={
        "L23_E": "L2/3_E",
        "L23_I": "L2/3_I",
    },
    marker_size=1.0,
    alpha=1.0,
    figsize=(4, 3),
    dpi=300,
    tick_label_size=5.0,
    axis_label_size=8.0,
    separator_lines=True,
    show_legend=False,
    invert_yaxis=True,
)


def main() -> None:
    simulation = Simulation.from_yaml(
        network_name=NETWORK_NAME,
        simulation_name=SIMULATION_NAME,
    )
    simulation.run()

    plot_raster(
        simulation,
        begin=RASTER_BEGIN,
        end=RASTER_END,
        area=RASTER_AREA,
        max_neurons_per_population=None,
        style=RASTER_STYLE,
    )


if __name__ == "__main__":
    main()
