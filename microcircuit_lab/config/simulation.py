"""What the simulation file may contain: run time, seeds, backend, recording and output."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from microcircuit_lab.config.frozen_config import FrozenConfig

#: Registered backend names. Adding a backend means adding it here and to
#: get_backend() and read_saved_spikes() in backends/__init__.py. See "Adding a
#: backend" in the README.
BackendName = Literal["nest", "brian2"]


class BackendConfig(FrozenConfig):
    """The simulator and its own options."""

    name: BackendName = Field(default="nest", description="the simulator to run the network with")
    options: dict[str, Any] = Field(
        default={},
        examples=[{"device": "cpp_standalone"}],
        description="options of that simulator, passed to its backend as-is; the backend "
        "validates them (see the simulator's section in the README)",
    )


class RecordingConfig(FrozenConfig):
    """What to record. The backend decides how."""

    spike_recording: bool = Field(default=True, description="record the spikes of every neuron")
    voltage_recording: bool = Field(default=False, description="record membrane potentials")
    voltage_interval: float = Field(
        default=1.0, gt=0.0, description="time between two voltage samples (ms)"
    )
    voltage_sample_size: int | None = Field(
        default=5,
        ge=1,
        description="neurons per population whose voltage is recorded; null records all",
    )


class OutputConfig(FrozenConfig):
    """Where and what to save.

    ``output_dir`` defaults to ``output/<network name>``, so runs of different
    networks never share a folder.
    """

    output_dir: Path | None = Field(
        default=None,
        examples=["output/pd14"],
        description="folder for the runs; omit for output/<network name>",
    )
    overwrite: bool = Field(
        default=False,
        description="false: each run gets its own <output_dir>/<date_time> folder; "
        "true: every run writes into output_dir itself",
    )
    save_metadata: bool = Field(
        default=True,
        description="write metadata.json (versions, spike counts, files written); "
        "needed with config.yaml to re-plot the run",
    )
    save_config: bool = Field(
        default=True,
        description="write config.yaml (the prepared network); needed to re-plot the run",
    )


class SimulationConfig(FrozenConfig):
    """How to run the simulation. The network itself is not described here."""

    t_sim: float = Field(default=100.0, gt=0.0, description="simulated time (ms)")
    resolution: float = Field(default=0.1, gt=0.0, description="simulation time step (ms)")
    rng_seed: int = Field(default=42, description="seed of the random numbers")
    local_num_threads: int = Field(default=1, ge=1, description="threads per process")
    print_time: bool = Field(default=True, description="print the simulation progress")
    backend: BackendConfig = Field(default=BackendConfig(), description="the simulator to use")
    recording: RecordingConfig = Field(default=RecordingConfig(), description="what to record")
    output: OutputConfig = Field(default=OutputConfig(), description="where and what to save")