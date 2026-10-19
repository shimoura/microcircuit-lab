"""
Spikes as two arrays, whatever simulator recorded them.

``senders`` (node IDs) and ``times`` (ms), sorted by sender, so that the spikes
of a population (a contiguous range of node IDs) are one slice. Each backend
reads its own files into this form; the rest of the core only sees these arrays.
"""

from __future__ import annotations

import numpy as np


def empty_spikes() -> tuple[np.ndarray, np.ndarray]:
    """No spikes: empty ``senders`` and ``times``."""

    return np.array([], dtype=int), np.array([], dtype=float)


def sort_by_sender(senders: np.ndarray, times: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The spikes sorted by sender (spikes of one sender keep their order)."""

    order = np.argsort(senders, kind="stable")
    return senders[order], times[order]


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
