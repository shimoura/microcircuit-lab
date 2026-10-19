"""
NEST's spike recordings on disk: reading them back.

NEST writes spikes to ascii files (``spikes-*.dat``, columns ``sender`` and
``time_ms``). A recorder that kept its events in memory is saved as
``spikes.csv`` with the same two columns. This module reads both. It does not
import ``nest``, so a saved run can be analysed without a simulator.

Spikes are returned as in ``backends/spikes.py``: ``senders`` and ``times``,
sorted by sender.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from microcircuit_lab.backends.spikes import empty_spikes, sort_by_sender




def ascii_spike_files(recordings_dir: Path) -> list[Path]:
    """The spike files NEST wrote to ``recordings_dir``, one per process or thread."""

    return sorted(Path(recordings_dir).glob("spikes-*.dat"))


def read_ascii_spikes(paths: list[Path]) -> tuple[np.ndarray, np.ndarray]:
    """The spikes of NEST's ascii files, sorted by sender."""

    if not paths:
        return empty_spikes()

    tables = [pd.read_csv(path, sep="\t", comment="#") for path in paths]
    senders = np.concatenate([table["sender"].to_numpy() for table in tables]).astype(int)
    times = np.concatenate([table["time_ms"].to_numpy() for table in tables]).astype(float)
    return sort_by_sender(senders, times)


def read_csv_spikes(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """The spikes of a ``spikes.csv``, sorted by sender."""

    table = pd.read_csv(path)
    senders = table["sender"].to_numpy(dtype=int)
    times = table["time_ms"].to_numpy(dtype=float)
    return sort_by_sender(senders, times)


def read_saved_spikes(recordings_dir: Path) -> tuple[np.ndarray, np.ndarray]:
    """
    The spikes a finished run saved under ``recordings_dir``, sorted by sender.

    Reads NEST's ascii files if there are any, else ``spikes.csv``.

    Raises
    ------
    ValueError
        If the folder has neither.
    """

    recordings_dir = Path(recordings_dir)
    paths = ascii_spike_files(recordings_dir)
    if paths:
        return read_ascii_spikes(paths)

    csv_path = recordings_dir / "spikes.csv"
    if csv_path.exists():
        return read_csv_spikes(csv_path)

    raise ValueError(
        f"No spike recordings under {recordings_dir} (expected 'spikes-*.dat' or "
        "'spikes.csv'). Simulate the run again with spike_recording enabled."
    )



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
