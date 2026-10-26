"""
Recording in the Brian2 backend: the monitors, and saving what they recorded.

Functions of ``Brian2Backend`` (``simulator.py``), kept here to keep that file
short; each takes the backend. Spikes are saved as ``spikes.csv`` and each
recorded variable as ``<variable>.csv``, in the layout of NEST's files.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import brian2 as b2
import numpy as np

from microcircuit_lab.backends import spikes

if TYPE_CHECKING:
    from microcircuit_lab.backends.brian2.simulator import Brian2Backend, _Group

#: The factor that gives a recorded variable in the unit of the config files
#: (mV, ms, pA, nS, Hz) from Brian2's base unit; any other dimension is saved in
#: Brian2's base unit.
RECORDING_SCALE = {
    b2.volt.dim: 1e3,
    b2.second.dim: 1e3,
    b2.amp.dim: 1e12,
    b2.siemens.dim: 1e9,
}


def create_spike_recorders(backend: Brian2Backend) -> None:
    """
    Create one spike monitor per group.
    """

    for group in backend._groups:
        backend.spike_recorders.append((group, b2.SpikeMonitor(group.neurons, name=f"{group.neurons.name}_spikes")))

def create_multimeters(backend: Brian2Backend) -> None:
    """
    Create, for each variable of ``recording.variables``, one state monitor
    per group: of the first ``sample_size`` neurons (all, if not set) of
    the populations the variable is recorded from.
    """

    recording = backend._simulation_config.recording
    for name, variable in recording.variables.items():
        recorded = recording.recorded_populations(name, backend.populations)
        backend.multimeters[name] = []
        for group in backend._groups:
            record = []
            for pop, start in zip(group.populations, group.starts):
                if pop in recorded:
                    size = backend._network.populations[pop].size
                    record.append(start + np.arange(min(variable.sample_size or size, size)))
            if record:
                monitor = b2.StateMonitor(
                    group.neurons, name, record=np.concatenate(record),
                    dt=variable.interval * b2.ms, name=f"{group.neurons.name}_{name}",
                )
                backend.multimeters[name].append((group, monitor))

def node_ids(backend: Brian2Backend, group: _Group, indices: np.ndarray) -> np.ndarray:
    """The NEST-style node IDs of neurons of a group, from their indices in it."""

    starts = np.asarray(group.starts)
    population = np.searchsorted(starts, indices, side="right") - 1
    first_ids = np.asarray([backend.first_ids[pop] for pop in group.populations])
    return first_ids[population] + indices - starts[population]

def load_spikes(backend: Brian2Backend) -> tuple[np.ndarray, np.ndarray]:
    """
    All spikes of the run as (senders, times), sorted by sender, with
    times as NEST gives them. Kept until the next simulate().
    """

    if backend._cached_spikes is not None:
        return backend._cached_spikes

    if not backend.spike_recorders:
        backend._cached_spikes = spikes.empty_spikes()
        return backend._cached_spikes

    senders = [node_ids(backend, group, np.asarray(monitor.i[:], dtype=int)) for group, monitor in backend.spike_recorders]
    # Brian2 gives a spike the time at the start of the step in which the
    # threshold is crossed, NEST the time at its end: one step later.
    step = backend._simulation_config.resolution
    times = [np.asarray(monitor.t / b2.ms, dtype=float) + step for _, monitor in backend.spike_recorders]
    backend._cached_spikes = spikes.sort_by_sender(np.concatenate(senders), np.concatenate(times))
    return backend._cached_spikes

def save_recordings(backend: Brian2Backend, run_dir: Path) -> list[Path]:
    """
    Write the spikes as ``recordings/spikes.csv`` and each recorded variable
    as ``recordings/<variable>.csv`` (columns ``sender``, ``time_ms`` and the
    variable's name, as NEST's files), and return the files.

    A variable is saved in the unit of the config files: mV, ms, pA, nS, Hz
    (spikes/s) or without a unit. Any other dimension is saved in Brian2's
    base unit (SI).
    """

    recordings_dir = Path(run_dir) / "recordings"
    recordings_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    if backend.spike_recorders:
        path = recordings_dir / "spikes.csv"
        spikes.write_csv_spikes(path, *load_spikes(backend))
        paths.append(path)

    for name, monitors in backend.multimeters.items():
        tables = []
        for group, monitor in monitors:
            # A sample at t is the state at t, as in NEST; NEST has no
            # sample at t = 0 (the initial state), so it is left out here too.
            after_start = np.asarray(monitor.t / b2.ms) > 0
            times = np.asarray(monitor.t / b2.ms)[after_start]
            senders = node_ids(backend, group, np.asarray(monitor.record))
            quantity = getattr(monitor, name)
            scale = RECORDING_SCALE.get(b2.get_dimensions(quantity), 1.0)
            values = np.asarray(quantity)[:, after_start] * scale
            tables.append(
                np.column_stack(
                    [np.repeat(senders, len(times)), np.tile(times, len(senders)), values.ravel()]
                )
            )
        path = recordings_dir / f"{name}.csv"
        np.savetxt(
            path,
            np.concatenate(tables),
            delimiter=",",
            header=f"sender,time_ms,{name}",
            comments="",
            fmt=["%d", "%.3f", "%.6g"],
        )
        paths.append(path)

    return paths
