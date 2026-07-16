"""Generic spike-raster plotting utilities."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import re

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

from .plot_styles import DEFAULT_RASTER_STYLE, RasterPlotConfig


def _select_populations(simulation, populations, area):
    available = list(simulation.network.config.populations)
    if populations is not None:
        missing = set(populations) - set(available)
        if missing:
            raise ValueError(f"Unknown populations: {sorted(missing)}")
        return list(populations)
    if area is not None:
        prefix = f"{area}__"
        selected = [name for name in available if name.startswith(prefix)]
        if not selected:
            raise ValueError(f"No populations found for area {area!r}.")
        return selected
    return available


def _population_metadata(name: str) -> tuple[str | None, str | None, str | None]:
    """Infer area, layer, and E/I type from conventional population names."""
    area, local_name = (
        (name.split("__", 1) + [None])[:2] if "__" in name else (None, name)
    )
    match = re.search(r"(?:^|_)(L(?:23|[1-6]))_([EI])(?:$|_)", local_name)
    if match:
        return area, match.group(1), match.group(2)
    cell_match = re.search(r"(?:^|_)([EI])(?:$|_)", local_name)
    return area, None, cell_match.group(1) if cell_match else None


def _tone(color: str, amount: float) -> tuple[float, float, float]:
    """Mix a color with white; 0 keeps the base color, 1 becomes white."""
    rgb = np.asarray(mcolors.to_rgb(color))
    return tuple(rgb + (1.0 - rgb) * amount)


def _population_color(name: str, index: int, style: RasterPlotConfig):
    _, layer, cell_type = _population_metadata(name)

    if style.color_mode == "custom":
        return style.custom_colors.get(name, f"C{index % 10}")
    if style.color_mode == "cell_type":
        return style.cell_type_colors.get(cell_type, f"C{index % 10}")
    if style.color_mode == "population":
        return f"C{index % 10}"

    base = style.layer_colors.get(layer, f"C{index % 10}")
    tone = style.excitatory_tone if cell_type == "E" else style.inhibitory_tone
    return _tone(base, tone) if cell_type in {"E", "I"} else base


def plot_raster(
    simulation,
    begin: float = 0.0,
    end: float | None = None,
    *,
    populations: Sequence[str] | None = None,
    area: str | None = None,
    max_neurons_per_population: int | None = 500,
    style: RasterPlotConfig | None = None,
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

    style = style or DEFAULT_RASTER_STYLE
    end = simulation.simulation_config.t_sim if end is None else end
    selected = _select_populations(simulation, populations, area)
    figsize = style.figsize or (
        style.width,
        max(style.min_height, style.height_per_population * len(selected)),
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
        color = _population_color(pop_name, index, style)

        if len(times):
            ax.plot(
                times,
                rows,
                "o",
                ms=style.marker_size,
                mew=0,
                alpha=style.alpha,
                color=color,
                rasterized=True,
            )

        local_name = pop_name.split("__", 1)[-1] if area is not None else pop_name
        label = style.population_labels.get(local_name, local_name)
        n_rows = len(nodes)
        yticks.append(offset + max(n_rows - 1, 0) / 2)
        ylabels.append(label)
        legend_handles.append(
            Line2D([0], [0], marker="o", linestyle="", color=color, label=label)
        )
        if index and style.separator_lines:
            ax.axhline(
                offset - 0.5, linewidth=0.5, alpha=style.separator_alpha, color="0.5"
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

    if style.invert_yaxis:
        ax.invert_yaxis()
    if style.show_legend and selected:
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
