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

from microcircuit_lab.backends.spikes import read_recording_files, read_spike_files


def ascii_spike_files(recordings_dir: Path) -> list[Path]:
    """The spike files NEST wrote to ``recordings_dir``, one per process or thread."""

    return sorted(Path(recordings_dir).glob("spikes-*.dat"))


def read_ascii_spikes(paths: list[Path]) -> tuple[np.ndarray, np.ndarray]:
    """The spikes of NEST's ascii files (tab-separated, with comment lines), sorted by sender."""

    return read_spike_files(paths, sep="\t", comment="#")


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
        return read_spike_files([csv_path])

    raise ValueError(
        f"No spike recordings under {recordings_dir} (expected 'spikes-*.dat' or "
        "'spikes.csv'). Simulate the run again with spike_recording enabled."
    )


def read_saved_variable(
    recordings_dir: Path, variable: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    A variable a finished run recorded, from NEST's files
    ``<variable>-*.dat`` (columns ``sender``, ``time_ms`` and the variable),
    as ``(senders, times, values)`` sorted by sender, then time.

    Raises
    ------
    ValueError
        If the folder has no file of that variable.
    """

    paths = sorted(Path(recordings_dir).glob(f"{variable}-*.dat"))
    if not paths:
        raise ValueError(
            f"No recording of {variable!r} under {recordings_dir} (expected "
            f"'{variable}-*.dat'). Simulate the run again with it in recording.variables."
        )
    return read_recording_files(paths, variable, sep="\t", comment="#")
