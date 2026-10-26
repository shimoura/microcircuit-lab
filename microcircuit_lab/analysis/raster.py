"""Generic spike-raster plotting utilities."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

from .areas import select_populations
from .plot_styles import (
    DEFAULT_PLOT_STYLE,
    DEFAULT_RASTER_CONFIG,
    PlotStyle,
    RasterPlotConfig,
    population_color,
    population_label,
)
from .run_command_plots import UNSET, register_plot


def plot_raster(
    run,
    begin: float = 0.0,
    end: float | None = None,
    *,
    populations: Sequence[str] | None = None,
    area: str | None = None,
    max_neurons_per_population: int | None = UNSET,
    style: PlotStyle | None = None,
    config: RasterPlotConfig | None = None,
    save_path: str | Path | None = None,
    show: bool = True,
):
    """
    Plot the spikes of each population (a raster plot).

    Parameters
    ----------
    run
        A finished run, from :func:`~microcircuit_lab.read_run`.
    begin, end
        The time window in ms; ``end`` defaults to the end of the run.
    populations
        Population names to use; by default all of them (or those of ``area``).
    area
        For a multi-area network, use only the populations of this area.
    max_neurons_per_population
        Show at most this many neurons per population (``None`` for all). By
        default from ``config``: ``neuron_fraction`` if set, else
        ``max_neurons_per_population``.
    style
        The shared plot style (:class:`~microcircuit_lab.config.PlotStyle`).
    config
        This plot's settings from the analysis file; its defaults otherwise.
    save_path
        Where to save the figure; not saved if ``None``.
    show
        Open the figure in a window.

    Returns
    -------
    tuple
        The matplotlib ``(figure, axes)``.

    Notes
    -----
    ``config.begin`` and ``config.end``, if set, replace ``begin`` and ``end``
    for this plot only.
    """
    style = style or DEFAULT_PLOT_STYLE
    config = config or DEFAULT_RASTER_CONFIG
    end = run.simulation.t_sim if end is None else end
    if config.begin is not None:
        begin = config.begin
    if config.end is not None:
        end = config.end
    selected = select_populations(run, populations, area)
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

    if max_neurons_per_population is UNSET:
        neuron_fraction = config.neuron_fraction
        fixed_cap = config.max_neurons_per_population
    else:
        neuron_fraction = None
        fixed_cap = max_neurons_per_population

    for index, pop_name in enumerate(selected):
        nodes = run.node_ids(pop_name)
        cap = max(1, round(neuron_fraction * len(nodes))) if neuron_fraction is not None else fixed_cap
        if cap is not None and len(nodes) > cap:
            keep = np.linspace(0, len(nodes) - 1, cap, dtype=int)
            nodes = nodes[keep]

        row_by_gid = {int(gid): offset + row for row, gid in enumerate(nodes)}
        senders, times = run.spikes(pop_name)
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

    margin = 0.05 * max(offset, 1)
    low, high = -0.5 - margin, offset - 0.5 + margin
    ax.set(xlim=(begin, end), ylim=(low, high), xlabel="Time (ms)", ylabel="Population")
    # A small population's band can be thinner than its label: move crowded
    # labels apart and join each to its band with a short line.
    axes_height_pt = fig.get_figheight() * ax.get_position().height * 72
    gap = 1.3 * style.tick_label_size * (high - low) / axes_height_pt
    label_positions = _spread(yticks, gap, low, high)
    ax.set_yticks(label_positions, ylabels)
    ax.tick_params(axis="both", labelsize=style.tick_label_size)
    ax.tick_params(axis="y", length=0)
    for band, label_y in zip(yticks, label_positions):
        ax.plot(
            [-0.015, 0.0], [label_y, band], transform=ax.get_yaxis_transform(),
            color="black", linewidth=0.6, clip_on=False,
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


def _spread(positions: list[float], gap: float, low: float, high: float) -> list[float]:
    """Move sorted ``positions`` as little as possible so that neighbours are at
    least ``gap`` apart, staying within ``[low, high]``. When there are too many
    labels for that gap, they are set closer, so they still fit: a label past
    the axis would make matplotlib widen the axis and squeeze the data."""

    if positions:
        gap = min(gap, (high - low) / len(positions))
    groups: list[list[float]] = []
    for position in positions:
        groups.append([position])
        while len(groups) > 1:
            first, second = groups[-2], groups[-1]
            if _group_start(first, gap) + gap * len(first) <= _group_start(second, gap):
                break
            groups[-2:] = [first + second]

    spread = []
    for group in groups:
        start = _group_start(group, gap)
        spread.extend(start + gap * index for index in range(len(group)))
    shift = max(0.0, low - spread[0]) if spread else 0.0
    shift -= max(0.0, spread[-1] + shift - high) if spread else 0.0
    return [position + shift for position in spread]


def _group_start(group: list[float], gap: float) -> float:
    """Where a group of labels ``gap`` apart starts when centred on its members."""

    return sum(group) / len(group) - gap * (len(group) - 1) / 2


register_plot("raster", config_cls=RasterPlotConfig, plot_fn=plot_raster, filename="raster.png")
