"""Repository-level convenience entrypoint for HuMAM runs."""

from microcircuit_lab.analysis import RasterPlotConfig
from microcircuit_lab.workflows.humam import HumamRunConfig, run_humam


# -----------------------------------------------------------------------------
# Scientist-friendly configuration
# -----------------------------------------------------------------------------
# Set AREA to "all" to run the full multi-area HuMAM network.
AREA = "all"

# Output config names written under configs/network/ and configs/simulation/.
NETWORK_NAME = "humam_all"
SIMULATION_NAME = "humam_all"

# Scaling and runtime controls.
N_SCALING = 0.004
K_SCALING = 0.004
T_SIM = 2000.0
THREADS = 16
RNG_SEED = 42

# Optional behaviors.
EXPORT_JSON = False
SKIP_GENERATE = False

# Area shown in the raster. Use None to disable plotting.
RASTER_AREA = "caudalanteriorcingulate"
RASTER_STYLE = RasterPlotConfig(
    color_mode="layer",
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
    run_humam(
        HumamRunConfig(
            area=AREA,
            network_name=NETWORK_NAME,
            simulation_name=SIMULATION_NAME,
            n_scaling=N_SCALING,
            k_scaling=K_SCALING,
            t_sim=T_SIM,
            threads=THREADS,
            rng_seed=RNG_SEED,
            export_json=EXPORT_JSON,
            skip_generate=SKIP_GENERATE,
            raster_area=RASTER_AREA,
            raster_style=RASTER_STYLE,
        )
    )


if __name__ == "__main__":
    main()
