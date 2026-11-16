"""
Save and load analysis results in a run directory, so a re-plot or a
comparison across runs can reuse them instead of recomputing from the spikes.

They are saved as ``.npz`` files, because they are numeric arrays (the spike
events themselves are stored as CSV).

Each value in ``measures`` is either a scalar (for example the firing rate of
a population) or a ``(freqs, power)`` pair of arrays (a power spectrum), with
the same ``freqs`` for all populations.

A file also keeps the settings its measures were computed with (time window,
populations, ...), so a result is only reused for the same settings.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import numpy as np


def _measures_path(run_dir: str | Path, name: str) -> Path:
    return Path(run_dir) / "measures" / f"{name}.npz"


def _as_text(settings: dict | None) -> str:
    """The settings as one line of text, to save in the file and to compare."""
    return json.dumps(settings or {}, sort_keys=True, default=str)


def save_measures(
    run_dir: str | Path, name: str, measures: dict, settings: dict | None = None
) -> Path:
    """
    Save computed measures in the run folder, as ``<run_dir>/measures/<name>.npz``.

    Parameters
    ----------
    run_dir
        The run folder.
    name
        The file name, without extension.
    measures
        ``{key: array}`` to save.
    settings
        What the measures were computed with (e.g. the time window), saved
        in the file.
    """

    path = _measures_path(run_dir, name)
    path.parent.mkdir(parents=True, exist_ok=True)

    populations = list(measures)
    first = measures[populations[0]]

    if isinstance(first, tuple):
        freqs, _ = first
        power = np.stack([measures[population][1] for population in populations])
        arrays = {"freqs": freqs, "power": power}
    else:
        arrays = {"values": [measures[population] for population in populations]}

    np.savez(path, populations=populations, settings=_as_text(settings), **arrays)

    return path


def load_measures(run_dir: str | Path, name: str, settings: dict | None = None) -> dict | None:
    """
    Load measures saved by :func:`save_measures`.

    Parameters
    ----------
    run_dir
        The run folder.
    name
        The name they were saved under.
    settings
        What the measures should have been computed with; by default, not
        compared.

    Returns
    -------
    dict or None
        ``{key: array}``, or ``None`` if there is no such file or it was
        computed with other settings.
    """

    path = _measures_path(run_dir, name)
    if not path.exists():
        return None

    data = np.load(path)
    if settings is not None:
        if "settings" not in data or str(data["settings"]) != _as_text(settings):
            return None

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
    settings: dict | None = None,
    *,
    recompute: bool = False,
    save: bool = True,
) -> dict:
    """
    Load saved measures, or compute and save them. Measures saved with other
    settings are computed again and replaced.

    Used by ``cached_population_firing_rates`` and ``cached_power_spectrum``.

    Parameters
    ----------
    run_dir
        The run folder.
    name
        The name the measures are saved under.
    compute
        A function without arguments that returns ``{key: array}``.
    settings
        Everything that changes the result of ``compute`` (e.g. the time
        window), as plain values.
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
        cached = load_measures(run_dir, name, settings)
        if cached is not None:
            return cached

    result = compute()
    if save:
        save_measures(run_dir, name, result, settings)
    return result
