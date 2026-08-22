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
    """Save `measures` to ``<run_dir>/measures/<name>.npz``."""

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
    """Load measures saved by :func:`save_measures`, or None if
    ``<run_dir>/measures/<name>.npz`` doesn't exist."""

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
    """Return :func:`load_measures`'s result if present and `recompute` is
    False; otherwise call `compute`, optionally :func:`save_measures` the
    result, and return that.

    The generic building block behind microcircuit_lab.analysis's
    cached_population_firing_rates/cached_power_spectrum.
    """

    if not recompute:
        cached = load_measures(run_dir, name)
        if cached is not None:
            return cached

    result = compute()
    if save:
        save_measures(run_dir, name, result)
    return result
