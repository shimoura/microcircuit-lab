"""
Brian2's spike recordings on disk: reading them back.

Brian2 keeps the spikes in memory, and a run saves them as ``spikes.csv``
(see ``backends/population_spikes.py``), and each recorded variable as
``<variable>.csv``. This module does not import
``brian2``, so a saved run can be analysed without it.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from microcircuit_lab.backends.population_spikes import read_csv_spikes, sort_recording


def read_saved_spikes(recordings_dir: Path) -> tuple[np.ndarray, np.ndarray]:
    """
    The spikes a finished run saved under ``recordings_dir``, sorted by sender.

    Raises
    ------
    ValueError
        If the folder has no ``spikes.csv``.
    """

    csv_path = Path(recordings_dir) / "spikes.csv"
    if not csv_path.exists():
        raise ValueError(
            f"No spike recordings under {recordings_dir} (expected 'spikes.csv'). "
            "Simulate the run again with spike_recording enabled."
        )
    return read_csv_spikes(csv_path)


def read_saved_variable(
    recordings_dir: Path, variable: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    A variable a finished run recorded, from ``<variable>.csv`` (columns
    ``sender``, ``time_ms`` and the variable), as ``(senders, times, values)``
    sorted by sender, then time.

    Raises
    ------
    ValueError
        If the folder has no file of that variable.
    """

    csv_path = Path(recordings_dir) / f"{variable}.csv"
    if not csv_path.exists():
        raise ValueError(
            f"No recording of {variable!r} under {recordings_dir} (expected "
            f"'{variable}.csv'). Simulate the run again with it in recording.variables."
        )
    table = pd.read_csv(csv_path)
    return sort_recording(
        table["sender"].to_numpy().astype(int),
        table["time_ms"].to_numpy().astype(float),
        table[variable].to_numpy().astype(float),
    )
