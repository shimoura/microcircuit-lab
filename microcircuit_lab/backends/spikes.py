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


def read_csv_spikes(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """The spikes of a ``spikes.csv``, sorted by sender."""

    table = pd.read_csv(path)
    senders = table["sender"].to_numpy(dtype=int)
    times = table["time_ms"].to_numpy(dtype=float)
    return sort_by_sender(senders, times)


def write_csv_spikes(path: Path, senders: np.ndarray, times: np.ndarray) -> None:
    """Write spikes to a ``spikes.csv``, ordered by time."""

    order = np.argsort(times)
    np.savetxt(
        path,
        np.column_stack([senders[order], times[order]]),
        delimiter=",",
        header="sender,time_ms",
        comments="",
        fmt=["%d", "%.3f"],
    )
