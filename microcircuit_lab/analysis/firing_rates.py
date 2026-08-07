"""Population firing-rate analysis and visualization."""

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


def compute_neuron_firing_rates(
    simulation,
    begin: float = 0.0,
    end: float | None = None,
    *,
    populations: Sequence[str] | None = None,
    area: str | None = None,
) -> dict[str, np.ndarray]:
    """Compute the firing rate of every neuron in each selected population."""
    if simulation.backend is None:
        raise RuntimeError("Simulation has not been run yet.")
    if not simulation.simulation_config.recording.spike_recording:
        raise RuntimeError("Spike recording is disabled for this simulation.")

    end = simulation.simulation_config.t_sim if end is None else end
    if end <= begin:
        raise ValueError("'end' must be greater than 'begin'.")

    selected = select_populations(simulation, populations, area)
    duration_s = (end - begin) / 1000.0
    rates: dict[str, np.ndarray] = {}

    for pop_name in selected:
        nodes = np.asarray(simulation.backend.get_population(pop_name).tolist(), dtype=int)
        events = simulation.backend.get_spike_events(pop_name)
        times = np.asarray(events["times"])
        senders = np.asarray(events["senders"], dtype=int)

        mask = (times >= begin) & (times < end)
        sender_counts = dict(zip(*np.unique(senders[mask], return_counts=True)))
        counts = np.fromiter(
            (sender_counts.get(gid, 0) for gid in nodes),
            dtype=float,
            count=len(nodes),
        )
        rates[pop_name] = counts / duration_s

    return rates


def compute_population_firing_rates(
    simulation,
    begin: float = 0.0,
    end: float | None = None,
    *,
    populations: Sequence[str] | None = None,
    area: str | None = None,
) -> dict[str, float]:
    """Compute the mean firing rate of each selected population."""
    neuron_rates = compute_neuron_firing_rates(
        simulation,
        begin,
        end,
        populations=populations,
        area=area,
    )
    return {name: float(values.mean()) for name, values in neuron_rates.items()}


def compute_reference_deviation(
    simulation,
    begin: float = 0.0,
    end: float | None = None,
    *,
    populations: Sequence[str] | None = None,
    area: str | None = None,
) -> dict[str, float]:
    """
    Relative deviation of simulated mean firing rates from published
    reference rates: ``(simulated - reference) / reference``.

    A programmatic counterpart to ``plot_firing_rates(..., show_reference=True)``
    -- for scripting a pass/fail check instead of eyeballing a plot.
    Raises if the network has no ``reference.full_mean_rates``, or a
    selected population isn't in it.
    """

    reference = simulation.network.config.reference
    if reference is None or not reference.full_mean_rates:
        raise ValueError("This network has no reference.full_mean_rates to validate against.")

    simulated = compute_population_firing_rates(
        simulation, begin, end, populations=populations, area=area
    )

    deviations = {}
    for name, rate in simulated.items():
        if name not in reference.full_mean_rates:
            raise ValueError(f"No reference rate for population {name!r}.")
        ref_rate = reference.full_mean_rates[name]
        deviations[name] = (rate - ref_rate) / ref_rate if ref_rate else float("inf")

    return deviations


def check_reference_rates(
    simulation,
    begin: float = 0.0,
    end: float | None = None,
    *,
    populations: Sequence[str] | None = None,
    area: str | None = None,
    rtol: float = 0.5,
) -> dict[str, float]:
    """
    Assert every selected population's simulated rate is within ``rtol``
    relative deviation of its published reference rate.

    Returns the deviations (see compute_reference_deviation) on success;
    raises AssertionError listing every population that failed otherwise.
    Reference rates are typically full-scale/unscaled published values,
    so a loose default tolerance is deliberate -- a scaled-down network
    isn't expected to match them precisely, only be in the right regime.
    """

    deviations = compute_reference_deviation(
        simulation, begin, end, populations=populations, area=area
    )

    failures = {name: dev for name, dev in deviations.items() if abs(dev) > rtol}
    if failures:
        details = ", ".join(f"{name}: {dev:+.1%}" for name, dev in failures.items())
        raise AssertionError(
            f"Simulated rates deviate from reference by more than {rtol:.0%} for: {details}"
        )

    return deviations


def plot_firing_rates(
    simulation,
    begin: float = 0.0,
    end: float | None = None,
    *,
    populations: Sequence[str] | None = None,
    area: str | None = None,
    show_reference: bool = False,
    style: PlotStyle | None = None,
    config: FiringRatePlotConfig | None = None,
    save_path: str | Path | None = None,
    show: bool = True,
    rng_seed: int = 0,
):
    """Plot per-neuron firing-rate distributions for selected populations."""
    style = style or DEFAULT_PLOT_STYLE
    config = config or DEFAULT_FIRING_RATE_CONFIG
    rates = compute_neuron_firing_rates(
        simulation, begin, end, populations=populations, area=area
    )
    names = list(rates)
    values = [rates[name] for name in names]
    positions = np.arange(len(names))
    colors = [population_color(name, i, style) for i, name in enumerate(names)]

    figsize = config.figsize or (
        config.width,
        max(config.min_height, config.height_per_population * len(names) + 1.0),
    )
    fig, ax = plt.subplots(figsize=figsize, dpi=style.dpi)

    violins = ax.violinplot(
        values, positions=positions, vert=False,
        showmeans=False, showmedians=False, showextrema=False,
    )
    for body, color in zip(violins["bodies"], colors):
        body.set_facecolor(color)
        body.set_edgecolor(color)
        body.set_alpha(config.violin_alpha)

    box = ax.boxplot(
        values, positions=positions, vert=False, widths=config.box_width,
        showfliers=False, patch_artist=True,
    )
    for patch, color in zip(box["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.18)
    for element in ("whiskers", "caps", "medians"):
        for artist in box[element]:
            artist.set_color("0.2")

    if config.show_points:
        rng = np.random.default_rng(rng_seed)
        for position, population_rates, color in zip(positions, values, colors):
            points = population_rates
            if len(points) > config.max_points_per_population:
                points = rng.choice(points, config.max_points_per_population, replace=False)
            jitter = rng.uniform(-0.07, 0.07, size=len(points))
            ax.scatter(
                points, position + jitter, s=config.point_size,
                alpha=config.point_alpha, color=color, edgecolors="none",
                rasterized=True,
            )

    if config.show_mean:
        for position, population_rates, color in zip(positions, values, colors):
            ax.scatter(
                population_rates.mean(), position, marker="D",
                s=config.mean_marker_size, color=color, edgecolor="none", zorder=4,
            )

    reference_plotted = False
    if show_reference:
        reference = simulation.network.config.reference
        if reference is not None:
            for position, name in zip(positions, names):
                if name in reference.full_mean_rates:
                    ax.scatter(
                        reference.full_mean_rates[name], position, marker="x",
                        s=45, linewidths=1.5, color="0.15", zorder=5,
                        label="Reference mean" if not reference_plotted else None,
                    )
                    reference_plotted = True

    labels = [population_label(name, style, strip_area=area is not None) for name in names]
    ax.set_yticks(positions, labels)
    ax.set_xlabel("Firing rate (spikes/s)", fontsize=style.axis_label_size)
    ax.set_ylabel("Population", fontsize=style.axis_label_size)
    ax.tick_params(axis="both", labelsize=style.tick_label_size)
    if config.invert_yaxis:
        ax.invert_yaxis()
    if config.show_legend and reference_plotted:
        ax.legend(frameon=False, fontsize=style.legend_size)
    fig.tight_layout()

    if save_path is not None:
        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=style.dpi, bbox_inches="tight")
    if show:
        plt.show()
    return fig, ax
