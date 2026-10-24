"""
Brian2's spike recordings on disk: reading them back.

Brian2 keeps the spikes in memory, and a run saves them as ``spikes.csv``
(see ``backends/population_spikes.py``). This module does not import
``brian2``, so a saved run can be analysed without it.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from microcircuit_lab.backends.population_spikes import read_csv_spikes


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
