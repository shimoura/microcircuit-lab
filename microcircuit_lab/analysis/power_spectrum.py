"""Population rate power-spectrum analysis and visualization.

Spectral estimation is pluggable: POWER_SPECTRUM_METHODS maps a method
name to an estimator function, the same registry pattern used for
simulator backends (microcircuit_lab.backends.get_backend) and model
generators (microcircuit_lab.generators.GENERATOR_REGISTRY). Add a new method
by registering it here; compute_power_spectrum/plot_power_spectrum never
need to change.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from microcircuit_lab.io.measures import load_or_compute

from ._utils import UNSET, select_populations
from .plot_styles import (
    DEFAULT_PLOT_STYLE,
    DEFAULT_POWER_SPECTRUM_CONFIG,
    PlotStyle,
    PowerSpectrumPlotConfig,
    population_color,
    population_label,
    population_metadata,
)
from .registry import register_plot

PowerSpectrumEstimator = Callable[..., tuple[np.ndarray, np.ndarray]]


def _periodogram(signal: np.ndarray, fs: float) -> tuple[np.ndarray, np.ndarray]:
    """Single-window FFT periodogram (no averaging -- noisiest, cheapest, highest resolution)."""

    signal = signal - signal.mean()
    n = len(signal)
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    power = np.abs(np.fft.rfft(signal)) ** 2 / (fs * n)
    if n > 1:
        power[1:-1] *= 2.0  # one-sided spectrum: fold negative frequencies in, DC/Nyquist excluded
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
    frequency resolution for variance -- wider means more, lower-variance
    tapers at the cost of a wider smoothing kernel; defaults to MNE's own
    ``8 * fs / n_samples``. `adaptive` uses adaptive taper weighting
    instead of a plain average (slower, generally more accurate).
    """

    try:
        from mne.time_frequency import psd_array_multitaper
    except ImportError as exc:
        raise ImportError(
            "method='multitaper' requires mne. Install it with e.g. `pip install mne`."
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
    simulation,
    begin: float,
    end: float,
    pop_name: str,
    bin_size: float,
) -> np.ndarray:
    """Bin one population's spikes into a population-rate (Hz) time series."""

    n_neurons = simulation.network.config.populations[pop_name].size
    events = simulation.backend.get_spike_events(pop_name)
    times = np.asarray(events["times"])
    times = times[(times >= begin) & (times < end)]

    edges = np.arange(begin, end + bin_size, bin_size)
    counts, _ = np.histogram(times, bins=edges)
    return counts / (n_neurons * (bin_size / 1000.0))


def compute_power_spectrum(
    simulation,
    begin: float = 0.0,
    end: float | None = None,
    *,
    populations: Sequence[str] | None = None,
    area: str | None = None,
    bin_size: float = 1.0,
    method: str = "welch",
    method_kwargs: dict | None = None,
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Compute the population-rate power spectrum for each selected population.

    Returns ``{population: (freqs_hz, power)}``. ``method`` selects the
    spectral estimator from :data:`POWER_SPECTRUM_METHODS`.
    """

    if simulation.backend is None:
        raise RuntimeError("Simulation has not been run yet.")
    if not simulation.simulation_config.recording.spike_recording:
        raise RuntimeError("Spike recording is disabled for this simulation.")
    if method not in POWER_SPECTRUM_METHODS:
        raise ValueError(
            f"Unknown power spectrum method {method!r}. "
            f"Available: {sorted(POWER_SPECTRUM_METHODS)}"
        )

    end = simulation.simulation_config.t_sim if end is None else end
    if end <= begin:
        raise ValueError("'end' must be greater than 'begin'.")

    selected = select_populations(simulation, populations, area)
    fs = 1000.0 / bin_size
    estimator = POWER_SPECTRUM_METHODS[method]
    method_kwargs = method_kwargs or {}

    spectra = {}
    for pop_name in selected:
        signal = compute_population_rate_signal(simulation, begin, end, pop_name, bin_size)
        spectra[pop_name] = estimator(signal, fs, **method_kwargs)

    return spectra


def cached_power_spectrum(
    simulation,
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
    """compute_power_spectrum, reusing a previous run's saved result (see
    microcircuit_lab.io.measures) under simulation.output_dir when present,
    instead of recomputing from spikes -- e.g. useful when iterating on how
    a comparison across several runs is plotted.

    Not derived from begin/end/populations/area/bin_size/method/
    method_kwargs -- pass recompute=True after changing any of those,
    since a stale cache won't reflect that.
    """

    if simulation.output_dir is None:
        raise RuntimeError(
            "Simulation has no output_dir -- run() or from_run_dir() it "
            "before requesting its cached power spectrum."
        )

    return load_or_compute(
        simulation.output_dir,
        "power_spectrum",
        lambda: compute_power_spectrum(
            simulation,
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
    simulation,
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
    """Plot the power spectrum of each selected population, arranged in a
    grid: populations that share a layer (see :func:`_grid_layout`) share a
    row, one column per cell type -- so e.g. ``L23_E``/``L23_I`` line up
    next to each other while ``L4_E``/``L4_I`` form the row below.

    The zero-frequency (DC) bin is never plotted -- after mean-detrending
    it carries no information, and it would break a log-scaled frequency
    axis (``config.log_freq``) anyway. ``xlim`` defaults to ``config.xlim``
    (the full frequency range, so keep it out of ``(0, ...)`` if
    ``log_freq`` is on); pass an explicit range, e.g. ``xlim=(1, 150)``, to
    zoom in. ``method``/``method_kwargs`` default to ``config.method``/
    ``config.method_kwargs`` (e.g. ``{"bandwidth": 4.0}`` for
    ``method="multitaper"``). Set ``config.log_power``/``config.log_freq``
    for a log or log-log plot.
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
        simulation,
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
            freqs, power = freqs[1:], power[1:]  # drop DC: meaningless after detrending
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
