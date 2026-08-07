"""Spike-train irregularity (ISI coefficient of variation) analysis.

CV ~ 0 is regular/clock-like firing, CV ~ 1 is Poisson-like (the
textbook "asynchronous irregular" cortical target regime), CV > 1 is
bursty. Mirrors firing_rates.py's compute/plot split and reuses
FiringRatePlotConfig -- the same per-population distribution layout
applies, just with a different quantity on the x-axis.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from ._utils import select_populations
from .plot_styles import (
    DEFAULT_FIRING_RATE_CONFIG,
    DEFAULT_PLOT_STYLE,
    FiringRatePlotConfig,
    PlotStyle,
    population_color,
    population_label,
)


def compute_neuron_isi_cv(
    simulation,
    begin: float = 0.0,
    end: float | None = None,
    *,
    populations: Sequence[str] | None = None,
    area: str | None = None,
    min_spikes: int = 3,
) -> dict[str, np.ndarray]:
    """Compute the ISI coefficient of variation for every neuron in each
    selected population.

    A neuron needs at least ``min_spikes`` spikes (i.e. at least
    ``min_spikes - 1`` inter-spike intervals) in ``[begin, end)`` for CV
    to be defined; neurons with fewer get NaN, so they're naturally
    excluded from NaN-aware aggregates (e.g. compute_population_isi_cv)
    without special-casing.
    """

    if simulation.backend is None:
        raise RuntimeError("Simulation has not been run yet.")
    if not simulation.simulation_config.recording.spike_recording:
        raise RuntimeError("Spike recording is disabled for this simulation.")

    end = simulation.simulation_config.t_sim if end is None else end
    if end <= begin:
        raise ValueError("'end' must be greater than 'begin'.")
    if min_spikes < 2:
        raise ValueError("'min_spikes' must be at least 2 (at least 1 ISI).")

    selected = select_populations(simulation, populations, area)
    cv_by_population: dict[str, np.ndarray] = {}

    for pop_name in selected:
        nodes = np.asarray(simulation.backend.get_population(pop_name).tolist(), dtype=int)
        events = simulation.backend.get_spike_events(pop_name)
        times = np.asarray(events["times"])
        senders = np.asarray(events["senders"], dtype=int)

        mask = (times >= begin) & (times < end)
        times, senders = times[mask], senders[mask]

        cvs = np.full(len(nodes), np.nan)
        row_by_gid = {int(gid): row for row, gid in enumerate(nodes)}

        order = np.argsort(senders)
        senders_sorted, times_sorted = senders[order], times[order]
        unique_senders, start_idx, counts = np.unique(
            senders_sorted, return_index=True, return_counts=True
        )

        for sender, start, count in zip(unique_senders, start_idx, counts):
            if count < min_spikes:
                continue
            row = row_by_gid.get(int(sender))
            if row is None:
                continue

            isi = np.diff(np.sort(times_sorted[start : start + count]))
            if isi.mean() > 0:
                cvs[row] = isi.std() / isi.mean()

        cv_by_population[pop_name] = cvs

    return cv_by_population


def compute_population_isi_cv(
    simulation,
    begin: float = 0.0,
    end: float | None = None,
    *,
    populations: Sequence[str] | None = None,
    area: str | None = None,
    min_spikes: int = 3,
) -> dict[str, float]:
    """Compute the mean ISI CV of each selected population, ignoring
    neurons with too few spikes for CV to be defined."""

    neuron_cv = compute_neuron_isi_cv(
        simulation, begin, end, populations=populations, area=area, min_spikes=min_spikes,
    )
    return {
        name: (float(np.nanmean(values)) if np.any(~np.isnan(values)) else float("nan"))
        for name, values in neuron_cv.items()
    }


def plot_isi_cv(
    simulation,
    begin: float = 0.0,
    end: float | None = None,
    *,
    populations: Sequence[str] | None = None,
    area: str | None = None,
    min_spikes: int = 3,
    style: PlotStyle | None = None,
    config: FiringRatePlotConfig | None = None,
    save_path: str | Path | None = None,
    show: bool = True,
):
    """Plot per-neuron ISI-CV distributions for selected populations.

    A dashed reference line at CV=1 marks the Poisson-like "asynchronous
    irregular" regime cortical models are usually compared against.
    """

    style = style or DEFAULT_PLOT_STYLE
    config = config or DEFAULT_FIRING_RATE_CONFIG
    cv = compute_neuron_isi_cv(
        simulation, begin, end, populations=populations, area=area, min_spikes=min_spikes,
    )
    names = list(cv)
    values = [cv[name] for name in names]
    positions = np.arange(len(names))
    colors = [population_color(name, i, style) for i, name in enumerate(names)]
    clean_values = [v[~np.isnan(v)] for v in values]

    figsize = config.figsize or (
        config.width,
        max(config.min_height, config.height_per_population * len(names) + 1.0),
    )
    fig, ax = plt.subplots(figsize=figsize, dpi=style.dpi)

    plot_positions = [p for p, v in zip(positions, clean_values) if len(v)]
    plot_values = [v for v in clean_values if len(v)]
    plot_colors = [c for c, v in zip(colors, clean_values) if len(v)]

    if plot_values:
        violins = ax.violinplot(
            plot_values, positions=plot_positions, vert=False,
            showmeans=False, showmedians=False, showextrema=False,
        )
        for body, color in zip(violins["bodies"], plot_colors):
            body.set_facecolor(color)
            body.set_edgecolor(color)
            body.set_alpha(config.violin_alpha)

        box = ax.boxplot(
            plot_values, positions=plot_positions, vert=False, widths=config.box_width,
            showfliers=False, patch_artist=True,
        )
        for patch, color in zip(box["boxes"], plot_colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.18)
        for element in ("whiskers", "caps", "medians"):
            for artist in box[element]:
                artist.set_color("0.2")

    if config.show_mean:
        for position, population_values, color in zip(positions, clean_values, colors):
            if len(population_values):
                ax.scatter(
                    population_values.mean(), position, marker="D",
                    s=config.mean_marker_size, color=color, edgecolor="none", zorder=4,
                )

    ax.axvline(1.0, color="0.5", linewidth=0.8, linestyle="--", zorder=1)

    labels = [population_label(name, style, strip_area=area is not None) for name in names]
    ax.set_yticks(positions, labels)
    ax.set_xlabel("ISI CV", fontsize=style.axis_label_size)
    ax.set_ylabel("Population", fontsize=style.axis_label_size)
    ax.tick_params(axis="both", labelsize=style.tick_label_size)
    if config.invert_yaxis:
        ax.invert_yaxis()
    fig.tight_layout()

    if save_path is not None:
        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=style.dpi, bbox_inches="tight")
    if show:
        plt.show()
    return fig, ax
