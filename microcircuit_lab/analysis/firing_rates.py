"""Population firing-rate analysis and visualization."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from microcircuit_lab.analysis.cache import load_or_compute

from .areas import select_populations
from .plot_styles import (
    DEFAULT_FIRING_RATE_CONFIG,
    DEFAULT_PLOT_STYLE,
    FiringRatePlotConfig,
    PlotStyle,
    population_color,
    population_label,
)
from .registry import register_plot


def compute_neuron_firing_rates(
    simulation,
    begin: float = 0.0,
    end: float | None = None,
    *,
    populations: Sequence[str] | None = None,
    area: str | None = None,
) -> dict[str, np.ndarray]:
    """
    The firing rate of every neuron, per population.

    Parameters
    ----------
    simulation
        A run, or a run folder opened with ``Simulation.from_run_dir``.
    begin, end
        The time window in ms; ``end`` defaults to the end of the simulation.
    populations
        Population names to use; by default all of them (or those of ``area``).
    area
        For a multi-area network, use only the populations of this area.

    Returns
    -------
    dict of str to numpy.ndarray
        ``{population: rate of each neuron}``, in spikes/s.
    """
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
    """
    The mean firing rate of each population.

    Parameters
    ----------
    simulation
        A run, or a run folder opened with ``Simulation.from_run_dir``.
    begin, end
        The time window in ms; ``end`` defaults to the end of the simulation.
    populations
        Population names to use; by default all of them (or those of ``area``).
    area
        For a multi-area network, use only the populations of this area.

    Returns
    -------
    dict of str to float
        ``{population: mean rate}``, in spikes/s.
    """
    neuron_rates = compute_neuron_firing_rates(
        simulation,
        begin,
        end,
        populations=populations,
        area=area,
    )
    return {name: float(values.mean()) for name, values in neuron_rates.items()}


def cached_population_firing_rates(
    simulation,
    begin: float = 0.0,
    end: float | None = None,
    *,
    populations: Sequence[str] | None = None,
    area: str | None = None,
    recompute: bool = False,
    save: bool = True,
) -> dict[str, float]:
    """
    Like :func:`compute_population_firing_rates`, but saved in the run folder and
    read back the next time (see :mod:`microcircuit_lab.analysis.cache`).

    Useful when re-plotting a comparison of many runs. The saved result does not
    know which window, populations or area it was computed for: pass
    ``recompute=True`` after changing them.

    Parameters
    ----------
    simulation
        A run, or a run folder opened with ``Simulation.from_run_dir``.
    begin, end
        The time window in ms; ``end`` defaults to the end of the simulation.
    populations
        Population names to use; by default all of them (or those of ``area``).
    area
        For a multi-area network, use only the populations of this area.
    recompute
        Compute again even if a saved result exists.
    save
        Save the result in the run folder.

    Returns
    -------
    dict of str to float
        ``{population: mean rate}``, in spikes/s.
    """

    if simulation.output_dir is None:
        raise RuntimeError(
            "Simulation has no output_dir -- run() or from_run_dir() it "
            "before requesting its cached firing rates."
        )

    return load_or_compute(
        simulation.output_dir,
        "firing_rates",
        lambda: compute_population_firing_rates(
            simulation, begin, end, populations=populations, area=area
        ),
        recompute=recompute,
        save=save,
    )


def compute_reference_deviation(
    simulation,
    begin: float = 0.0,
    end: float | None = None,
    *,
    populations: Sequence[str] | None = None,
    area: str | None = None,
) -> dict[str, float]:
    """
    How far each population's mean rate is from its reference rate.

    The reference rates are ``full_mean_rates`` in the network's
    ``reference.yaml``. This is the number behind
    ``plot_firing_rates(..., show_reference=True)``, for a check in a script.

    Parameters
    ----------
    simulation
        A run, or a run folder opened with ``Simulation.from_run_dir``.
    begin, end
        The time window in ms; ``end`` defaults to the end of the simulation.
    populations
        Population names to use; by default all of them (or those of ``area``).
    area
        For a multi-area network, use only the populations of this area.

    Returns
    -------
    dict of str to float
        ``{population: (simulated - reference) / reference}``.

    Raises
    ------
    ValueError
        If the network has no reference rates, or none for a selected population.
    """

    reference = simulation.network.reference
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
    Check that every population's mean rate is within ``rtol`` of its reference.

    Reference rates are usually full-scale published values, so the default
    tolerance is loose: a downscaled network is expected to be in the right
    regime, not to match them exactly.

    Parameters
    ----------
    simulation
        A run, or a run folder opened with ``Simulation.from_run_dir``.
    begin, end
        The time window in ms; ``end`` defaults to the end of the simulation.
    populations
        Population names to use; by default all of them (or those of ``area``).
    area
        For a multi-area network, use only the populations of this area.
    rtol
        The largest allowed relative deviation (0.5 means 50 %).

    Returns
    -------
    dict of str to float
        The deviations, as in :func:`compute_reference_deviation`.

    Raises
    ------
    AssertionError
        Listing every population outside the tolerance.
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
    """
    Plot the distribution of single-neuron firing rates of each population.

    Parameters
    ----------
    simulation
        A run, or a run folder opened with ``Simulation.from_run_dir``.
    begin, end
        The time window in ms; ``end`` defaults to the end of the simulation.
    populations
        Population names to use; by default all of them (or those of ``area``).
    area
        For a multi-area network, use only the populations of this area.
    show_reference
        Overlay the reference rates (``reference.yaml``) as markers.
    style
        The shared plot style (:class:`~microcircuit_lab.config.PlotStyle`).
    config
        This plot's settings from the analysis file; its defaults otherwise.
    save_path
        Where to save the figure; not saved if ``None``.
    show
        Open the figure in a window.
    rng_seed
        Seed for choosing which points to show (when there are many) and
        for their horizontal jitter.

    Returns
    -------
    tuple
        The matplotlib ``(figure, axes)``.
    """
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
        values, positions=positions, orientation="horizontal",
        showmeans=False, showmedians=False, showextrema=False,
    )
    for body, color in zip(violins["bodies"], colors):
        body.set_facecolor(color)
        body.set_edgecolor(color)
        body.set_alpha(config.violin_alpha)

    box = ax.boxplot(
        values, positions=positions, orientation="horizontal", widths=config.box_width,
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
        reference = simulation.network.reference
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


register_plot(
    "firing_rates", config_cls=FiringRatePlotConfig, plot_fn=plot_firing_rates,
    filename="firing_rates.png",
)
