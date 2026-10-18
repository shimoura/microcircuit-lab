"""
Saving/loading computed analysis results tied to a run directory, so a
later process (a re-plot, a comparison across runs) can reuse them
instead of recomputing from spikes.

Saved as .npz -- these are numeric arrays, not the relational spike-event
data microcircuit_lab.backends.post_hoc uses CSV for.

Generic over shape: each value in `measures` is either a scalar (e.g.
compute_population_firing_rates's per-population rate) or a (freqs, power)
array pair (e.g. compute_power_spectrum's), with freqs assumed identical
across populations.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np


def _measures_path(run_dir: str | Path, name: str) -> Path:
    return Path(run_dir) / "measures" / f"{name}.npz"


def save_measures(run_dir: str | Path, name: str, measures: dict) -> Path:
    """
    Save computed measures in the run folder, as ``<run_dir>/measures/<name>.npz``.

    Parameters
    ----------
    run_dir
        The run folder.
    name
        The file name, without extension; include anything that changes the
        result (e.g. the area or the time window).
    measures
        ``{key: array}`` to save.
    """

    path = _measures_path(run_dir, name)
    path.parent.mkdir(parents=True, exist_ok=True)

    populations = list(measures)
    first = measures[populations[0]]

    if isinstance(first, tuple):
        freqs, _ = first
        power = np.stack([measures[population][1] for population in populations])
        np.savez(path, populations=populations, freqs=freqs, power=power)
    else:
        values = [measures[population] for population in populations]
        np.savez(path, populations=populations, values=values)

    return path


def load_measures(run_dir: str | Path, name: str) -> dict | None:
    """
    Load measures saved by :func:`save_measures`.

    Parameters
    ----------
    run_dir
        The run folder.
    name
        The name they were saved under.

    Returns
    -------
    dict or None
        ``{key: array}``, or ``None`` if there is no such file.
    """

    path = _measures_path(run_dir, name)
    if not path.exists():
        return None

    data = np.load(path)
    populations = data["populations"].tolist()

    if "freqs" in data:
        return {
            population: (data["freqs"], data["power"][i])
            for i, population in enumerate(populations)
        }
    return {
        population: float(value) for population, value in zip(populations, data["values"])
    }


def load_or_compute(
    run_dir: str | Path,
    name: str,
    compute: Callable[[], dict],
    *,
    recompute: bool = False,
    save: bool = True,
) -> dict:
    """
    Load saved measures, or compute and save them.

    Used by ``cached_population_firing_rates`` and ``cached_power_spectrum``.

    Parameters
    ----------
    run_dir
        The run folder.
    name
        The name the measures are saved under.
    compute
        A function without arguments that returns ``{key: array}``.
    recompute
        Compute even if saved measures exist.
    save
        Save what was computed.

    Returns
    -------
    dict
        ``{key: array}``.
    """

    if not recompute:
        cached = load_measures(run_dir, name)
        if cached is not None:
            return cached

    result = compute()
    if save:
        save_measures(run_dir, name, result)
    return result
