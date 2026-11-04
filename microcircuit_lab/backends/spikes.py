"""
Spikes as two arrays, whatever simulator recorded them.

``senders`` (node IDs) and ``times`` (ms), sorted by sender, so that the spikes
of a population (a contiguous range of node IDs) are one slice. Each backend
reads its own files into this form (``<simulator>/spike_files.py``); the rest of
the core only sees these arrays. Spikes kept in memory are saved as
``spikes.csv`` (columns ``sender`` and ``time_ms``), written and read here for
every backend.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def empty_spikes() -> tuple[np.ndarray, np.ndarray]:
    """No spikes: empty ``senders`` and ``times``."""

    return np.array([], dtype=int), np.array([], dtype=float)


def sort_by_sender(senders: np.ndarray, times: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The spikes sorted by sender (spikes of one sender keep their order)."""

    order = np.argsort(senders, kind="stable")
    return senders[order], times[order]


def sort_recording(
    senders: np.ndarray, times: np.ndarray, values: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The samples of a recorded variable sorted by sender, then by time."""

    order = np.lexsort((times, senders))
    return senders[order], times[order], values[order]


def spikes_in_id_range(
    senders: np.ndarray, times: np.ndarray, first_id: int, last_id: int
) -> dict:
    """
    The spikes of the neurons with node IDs ``first_id`` to ``last_id``
    (included), as ``{"senders": ..., "times": ...}``.

    ``senders`` must be sorted, as the functions above return them.
    """

    left = np.searchsorted(senders, first_id, side="left")
    right = np.searchsorted(senders, last_id + 1, side="left")
    return {"senders": senders[left:right], "times": times[left:right]}


def _read_columns(paths: list[Path], columns: list[str], csv_options: dict) -> list[np.ndarray]:
    """The named columns of one or more files of the same kind, joined in file order."""

    tables = [pd.read_csv(path, usecols=columns, **csv_options) for path in paths]
    return [np.concatenate([table[column].to_numpy() for table in tables]) for column in columns]


def read_spike_files(paths: list[Path], **csv_options) -> tuple[np.ndarray, np.ndarray]:
    """
    The spikes of files with the columns ``sender`` and ``time_ms`` (e.g. one
    per thread), sorted by sender. ``csv_options`` describe the files to
    ``pandas.read_csv``: none for a ``spikes.csv``, a tab separator and comment
    lines for NEST's ascii files.
    """

    if not paths:
        return empty_spikes()
    senders, times = _read_columns(paths, ["sender", "time_ms"], csv_options)
    return sort_by_sender(senders.astype(int), times.astype(float))


def read_recording_files(
    paths: list[Path], variable: str, **csv_options
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    The samples of a recorded variable, from files with the columns
    ``sender``, ``time_ms`` and ``variable``, as ``(senders, times, values)``
    sorted by sender, then time. ``csv_options`` as in :func:`read_spike_files`.
    """

    senders, times, values = _read_columns(paths, ["sender", "time_ms", variable], csv_options)
    return sort_recording(senders.astype(int), times.astype(float), values.astype(float))


def time_format(resolution: float) -> str:
    """
    The format of times (ms) in saved files: three decimals, as NEST writes
    them, or more when the time step has more (e.g. 0.0125 ms, which Brian2
    allows), so that no time is rounded.
    """

    decimals = len(np.format_float_positional(resolution, trim="-").partition(".")[2])
    return f"%.{max(3, decimals)}f"


def write_csv_spikes(path: Path, senders: np.ndarray, times: np.ndarray, resolution: float) -> None:
    """Write spikes to a ``spikes.csv``, ordered by time, with the decimals
    the time step ``resolution`` (ms) needs."""

    order = np.argsort(times)
    np.savetxt(
        path,
        np.column_stack([senders[order], times[order]]),
        delimiter=",",
        header="sender,time_ms",
        comments="",
        fmt=["%d", time_format(resolution)],
    )
