"""Population rate power-spectrum analysis and visualization.

The spectral method can be chosen by name: ``POWER_SPECTRUM_METHODS`` maps a
method name to an estimator function. To add a method, add it to that
dictionary; ``compute_power_spectrum`` and ``plot_power_spectrum`` stay as
they are.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from microcircuit_lab.analysis.measure_files import load_or_compute

from .areas import select_populations
from .plot_styles import (
    DEFAULT_PLOT_STYLE,
    DEFAULT_POWER_SPECTRUM_CONFIG,
    PlotStyle,
    PowerSpectrumPlotConfig,
    population_color,
    population_label,
    population_metadata,
)
from .run_command_plots import UNSET, register_plot
from .time_window import resolve_end

PowerSpectrumEstimator = Callable[..., tuple[np.ndarray, np.ndarray]]


def _periodogram(signal: np.ndarray, fs: float) -> tuple[np.ndarray, np.ndarray]:
    """Single-window FFT periodogram: no averaging, so the noisiest but the cheapest, with the highest resolution."""

    signal = signal - signal.mean()
    n = len(signal)
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    power = np.abs(np.fft.rfft(signal)) ** 2 / (fs * n)
    if n > 1:
        # One-sided spectrum: fold the negative frequencies in, leaving DC and Nyquist as they are.
        power[1:-1] *= 2.0
    return freqs, power


def _welch(
    signal: np.ndarray,
    fs: float,
    *,
    nperseg: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Welch's method: average periodograms of overlapping Hann-windowed segments.

    Lower variance than a single periodogram, at the cost of frequency
    resolution. Segment length defaults to min(256, len(signal)) samples
    with 50% overlap, matching scipy.signal.welch's defaults.
    """

    signal = signal - signal.mean()
    n = len(signal)
    nperseg = max(8, min(nperseg or min(256, n), n))
    step = nperseg - nperseg // 2
    window = np.hanning(nperseg)
    window_power = (window**2).sum()

    starts = range(0, max(n - nperseg, 0) + 1, step)
    segments = [signal[start : start + nperseg] * window for start in starts]
    if not segments:
        segments = [np.pad(signal, (0, nperseg - n)) * window]

    freqs = np.fft.rfftfreq(nperseg, d=1.0 / fs)
    power = np.zeros(len(freqs))
    for segment in segments:
        power += np.abs(np.fft.rfft(segment)) ** 2
    power /= len(segments) * fs * window_power
    if nperseg > 1:
        power[1:-1] *= 2.0

    return freqs, power


def _multitaper(
    signal: np.ndarray,
    fs: float,
    *,
    bandwidth: float | None = None,
    adaptive: bool = False,
    low_bias: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Multitaper method (DPSS/Slepian tapers), via mne.time_frequency.psd_array_multitaper.

    Lower variance than a single periodogram or Welch's method, without
    cutting the signal into shorter segments. `bandwidth` (Hz) trades
    frequency resolution for variance: a wider bandwidth uses more tapers
    and gives a lower variance, but smooths over a wider range of
    frequencies. It defaults to MNE's own ``8 * fs / n_samples``. `adaptive` uses adaptive taper weighting
    instead of a plain average (slower, generally more accurate).
    """

    try:
        from mne.time_frequency import psd_array_multitaper
    except ImportError as exc:
        raise ImportError(
            "method='multitaper' requires mne. Install it with "
            '`pip install "microcircuit_lab[multitaper]"`.'
        ) from exc

    power, freqs = psd_array_multitaper(
        signal,
        sfreq=fs,
        bandwidth=bandwidth,
        adaptive=adaptive,
        low_bias=low_bias,
        normalization="full",
        verbose=False,
    )
    return freqs, power


#: Registered spectral estimators, keyed by method name. Each takes
#: (signal, fs, **method_kwargs) and returns (freqs, power). Register a
#: new one by adding an entry here.
POWER_SPECTRUM_METHODS: dict[str, PowerSpectrumEstimator] = {
    "welch": _welch,
    "periodogram": _periodogram,
    "multitaper": _multitaper,
}


def compute_population_rate_signal(
    run,
    begin: float,
    end: float,
    pop_name: str,
    bin_size: float,
) -> np.ndarray:
    """
    One population's spikes binned into a population rate over time.

    Parameters
    ----------
    run
        A finished run, from :func:`~microcircuit_lab.read_run`.
    begin, end
        The time window in ms.
    pop_name
        The population.
    bin_size
        The bin width in ms. Only whole bins are used, from ``begin``: a
        remainder shorter than one bin at the end is left out.

    Returns
    -------
    numpy.ndarray
        The population rate in each bin, in spikes/s.
    """

    n_neurons = run.network.populations[pop_name].size
    _, times = run.spikes(pop_name)
    times = times[(times >= begin) & (times < end)]

    n_bins = int(np.floor((end - begin) / bin_size + 1e-9))
    edges = begin + bin_size * np.arange(n_bins + 1)
    counts, _ = np.histogram(times, bins=edges)
    return counts / (n_neurons * (bin_size / 1000.0))


def compute_power_spectrum(
    run,
    begin: float = 0.0,
    end: float | None = None,
    *,
    populations: Sequence[str] | None = None,
    area: str | None = None,
    bin_size: float = 1.0,
    method: str = "welch",
    method_kwargs: dict | None = None,
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """
    The power spectrum of each population's rate.

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
    bin_size
        The bin width of the rate signal, in ms.
    method
        The estimator: a name in :data:`POWER_SPECTRUM_METHODS` (``"welch"``,
        ``"periodogram"``, ``"multitaper"``).
    method_kwargs
        Extra arguments for the estimator, e.g. ``{"bandwidth": 4.0}`` for
        ``"multitaper"``.

    Returns
    -------
    dict of str to tuple
        ``{population: (frequencies in Hz, power)}``.
    """

    if method not in POWER_SPECTRUM_METHODS:
        raise ValueError(
            f"Unknown power spectrum method {method!r}. "
            f"Available: {sorted(POWER_SPECTRUM_METHODS)}"
        )

    end = resolve_end(run, begin, end)

    selected = select_populations(run, populations, area)
    fs = 1000.0 / bin_size
    estimator = POWER_SPECTRUM_METHODS[method]
    method_kwargs = method_kwargs or {}

    spectra = {}
    for pop_name in selected:
        signal = compute_population_rate_signal(run, begin, end, pop_name, bin_size)
        spectra[pop_name] = estimator(signal, fs, **method_kwargs)

    return spectra


def cached_power_spectrum(
    run,
    begin: float = 0.0,
    end: float | None = None,
    *,
    populations: Sequence[str] | None = None,
    area: str | None = None,
    bin_size: float = 1.0,
    method: str = "welch",
    method_kwargs: dict | None = None,
    recompute: bool = False,
    save: bool = True,
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """
    Like :func:`compute_power_spectrum`, but saved in the run folder and read
    back the next time (see :mod:`microcircuit_lab.analysis.measure_files`).

    The saved result does not know which settings it was computed with: pass
    ``recompute=True`` after changing them.

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
    bin_size, method, method_kwargs
        As in :func:`compute_power_spectrum`.
    recompute
        Compute again even if a saved result exists.
    save
        Save the result in the run folder.

    Returns
    -------
    dict of str to tuple
        ``{population: (frequencies in Hz, power)}``.
    """

    return load_or_compute(
        run.folder,
        "power_spectrum",
        lambda: compute_power_spectrum(
            run,
            begin,
            end,
            populations=populations,
            area=area,
            bin_size=bin_size,
            method=method,
            method_kwargs=method_kwargs,
        ),
        recompute=recompute,
        save=save,
    )


def _grid_layout(names: list[str]) -> dict[tuple[int, int], list[str]]:
    """
    Group populations into a (row, column) grid: populations that share a
    layer (e.g. ``L23_E``/``L23_I``, via the same naming convention used
    for coloring in :func:`population_color`) land in the same row, in
    the order layers/cell-types are first encountered. Populations without
    a recognized layer (e.g. a plain ``E``/``I`` toy network) all share
    one row instead, one column per cell type.
    """

    row_keys: list[tuple] = []
    col_keys: list[str] = []
    cells: dict[tuple[int, int], list[str]] = {}

    for name in names:
        area, layer, cell_type = population_metadata(name)
        row_key = (area, layer) if layer is not None else (area, None)
        col_key = cell_type if cell_type is not None else name

        if row_key not in row_keys:
            row_keys.append(row_key)
        if col_key not in col_keys:
            col_keys.append(col_key)

        position = (row_keys.index(row_key), col_keys.index(col_key))
        cells.setdefault(position, []).append(name)

    return cells


def plot_power_spectrum(
    run,
    begin: float = 0.0,
    end: float | None = None,
    *,
    populations: Sequence[str] | None = None,
    area: str | None = None,
    bin_size: float = 1.0,
    method: str = UNSET,
    method_kwargs: dict | None = UNSET,
    xlim: tuple[float, float] | None = UNSET,
    style: PlotStyle | None = None,
    config: PowerSpectrumPlotConfig | None = None,
    save_path: str | Path | None = None,
    show: bool = True,
):
    """
    Plot the power spectrum of each population, in a grid: one row per layer,
    one column per cell type (``L23_E`` next to ``L23_I``, ``L4_E`` below).

    The zero-frequency bin is never plotted: after removing the mean it carries
    no information, and it would break a log frequency axis.

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
    bin_size
        The bin width of the rate signal, in ms.
    method, method_kwargs
        The estimator, as in :func:`compute_power_spectrum`; by default as set in
        ``config``.
    xlim
        The frequency range to show, e.g. ``(1, 150)``; by default as set in
        ``config`` (the full range). Keep 0 out of it with ``config.log_freq``.
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
    """

    style = style or DEFAULT_PLOT_STYLE
    config = config or DEFAULT_POWER_SPECTRUM_CONFIG
    if xlim is UNSET:
        xlim = config.xlim
    if method is UNSET:
        method = config.method
    if method_kwargs is UNSET:
        method_kwargs = config.method_kwargs
    spectra = compute_power_spectrum(
        run,
        begin,
        end,
        populations=populations,
        area=area,
        bin_size=bin_size,
        method=method,
        method_kwargs=method_kwargs,
    )
    names = list(spectra)

    cells = _grid_layout(names)
    n_rows = max(row for row, _ in cells) + 1
    n_cols = max(col for _, col in cells) + 1

    figsize = config.figsize or (
        max(config.min_width, config.width_per_column * n_cols),
        max(config.min_height, config.height_per_row * n_rows),
    )
    fig, axes = plt.subplots(
        n_rows, n_cols, figsize=figsize, dpi=style.dpi, sharex=True, squeeze=False,
    )

    used_axes = set()
    for (row, col), cell_names in cells.items():
        ax = axes[row][col]
        used_axes.add((row, col))

        for pop_name in cell_names:
            freqs, power = spectra[pop_name]
            # Drop the DC bin: it carries no information after detrending.
            freqs, power = freqs[1:], power[1:]
            color = population_color(pop_name, names.index(pop_name), style)
            label = population_label(pop_name, style, strip_area=area is not None)
            ax.plot(freqs, power, color=color, linewidth=config.linewidth, label=label)

        if config.log_power:
            ax.set_yscale("log")
        if config.log_freq:
            ax.set_xscale("log")
        if xlim is not None:
            ax.set_xlim(xlim)

        title = ", ".join(
            population_label(name, style, strip_area=area is not None) for name in cell_names
        )
        ax.set_title(title, fontsize=style.axis_label_size)
        ax.tick_params(axis="both", labelsize=style.tick_label_size)
        if col == 0:
            ax.set_ylabel("Power", fontsize=style.axis_label_size)
        if len(cell_names) > 1:
            ax.legend(frameon=False, fontsize=style.legend_size)

    for row in range(n_rows):
        for col in range(n_cols):
            if (row, col) not in used_axes:
                axes[row][col].axis("off")

    for col in range(n_cols):
        for row in reversed(range(n_rows)):
            if (row, col) in used_axes:
                axes[row][col].set_xlabel("Frequency (Hz)", fontsize=style.axis_label_size)
                break

    fig.suptitle(f"Power spectrum ({method})", fontsize=style.title_size)
    fig.tight_layout()

    if save_path is not None:
        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=style.dpi, bbox_inches="tight")
    if show:
        plt.show()
    return fig, axes


register_plot(
    "power_spectrum", config_cls=PowerSpectrumPlotConfig, plot_fn=plot_power_spectrum,
    filename="power_spectrum.png",
)
