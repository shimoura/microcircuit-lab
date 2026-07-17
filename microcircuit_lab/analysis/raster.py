"""Generic spike-raster plotting utilities."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

from ._utils import select_populations
from .plot_styles import (
    DEFAULT_PLOT_STYLE,
    DEFAULT_RASTER_CONFIG,
    PlotStyle,
    RasterPlotConfig,
    population_color,
    population_label,
)


def plot_raster(
    simulation,
    begin: float = 0.0,
    end: float | None = None,
    *,
    populations: Sequence[str] | None = None,
    area: str | None = None,
    max_neurons_per_population: int | None = None,
    style: PlotStyle | None = None,
    config: RasterPlotConfig | None = None,
    save_path: str | Path | None = None,
    show: bool = True,
):
    """Plot recorded spikes for any network configuration.

    Population selection is independent of presentation. ``area`` supports the
    generic ``<group>__<population>`` naming convention used by multi-area
    configurations; ``style`` controls colors and figure appearance.
    """
    if simulation.backend is None:
        raise RuntimeError("Simulation has not been run yet.")
    if not simulation.simulation_config.recording.spike_recording:
        raise RuntimeError("Spike recording is disabled for this simulation.")

    style = style or DEFAULT_PLOT_STYLE
    config = config or DEFAULT_RASTER_CONFIG
    end = simulation.simulation_config.t_sim if end is None else end
    selected = select_populations(simulation, populations, area)
    figsize = config.figsize or (
        config.width,
        max(config.min_height, config.height_per_population * len(selected)),
    )
    fig, ax = plt.subplots(
        figsize=figsize,
        dpi=style.dpi,
    )
    yticks, ylabels, legend_handles = [], [], []
    offset = 0

    for index, pop_name in enumerate(selected):
        nodes = np.asarray(simulation.backend.get_population(pop_name).tolist())
        if (
            max_neurons_per_population is not None
            and len(nodes) > max_neurons_per_population
        ):
            keep = np.linspace(0, len(nodes) - 1, max_neurons_per_population, dtype=int)
            nodes = nodes[keep]

        row_by_gid = {int(gid): offset + row for row, gid in enumerate(nodes)}
        events = simulation.backend.get_spike_events(pop_name)
        times = np.asarray(events["times"])
        senders = np.asarray(events["senders"])
        mask = (times >= begin) & (times <= end) & np.isin(senders, nodes)
        times, senders = times[mask], senders[mask]
        rows = np.fromiter((row_by_gid[int(gid)] for gid in senders), dtype=int)
        color = population_color(pop_name, index, style)

        if len(times):
            ax.plot(
                times,
                rows,
                "o",
                ms=config.marker_size,
                mew=0,
                alpha=config.alpha,
                color=color,
                rasterized=True,
            )

        label = population_label(pop_name, style, strip_area=area is not None)
        n_rows = len(nodes)
        yticks.append(offset + max(n_rows - 1, 0) / 2)
        ylabels.append(label)
        legend_handles.append(
            Line2D([0], [0], marker="o", linestyle="", color=color, label=label)
        )
        if index and config.separator_lines:
            ax.axhline(
                offset - 0.5, linewidth=0.5, alpha=config.separator_alpha, color="0.5"
            )
        offset += n_rows

    ax.set(xlim=(begin, end), xlabel="Time (ms)", ylabel="Population")
    ax.set_yticks(yticks, ylabels)
    ax.tick_params(
        axis="both",
        labelsize=style.tick_label_size,
    )
    ax.xaxis.label.set_size(style.axis_label_size)
    ax.yaxis.label.set_size(style.axis_label_size)

    if config.invert_yaxis:
        ax.invert_yaxis()
    if config.show_legend and selected:
        ax.legend(
            handles=legend_handles,
            bbox_to_anchor=(1.02, 1),
            loc="upper left",
            frameon=False,
        )
    fig.tight_layout()

    if save_path is not None:
        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=style.dpi, bbox_inches="tight")
    if show:
        plt.show()
    return fig, ax
