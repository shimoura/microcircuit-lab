"""
Simulation configuration models.

This module defines immutable configuration objects describing how a
simulation should be executed.

The parameters describe execution settings such as simulation time, random seeds,
recording options and output locations.
"""

from __future__ import annotations
from pathlib import Path
from pydantic import Field

from microcircuit_lab.config.base import FrozenConfig

# -----------------------------------------------------------------------------
# Recording
# -----------------------------------------------------------------------------
class RecordingConfig(FrozenConfig):
    """
    Configuration of recording devices.
    Individual simulator backends decide how these requests are implemented.
    """

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


# -----------------------------------------------------------------------------
# Output
# -----------------------------------------------------------------------------
class OutputConfig(FrozenConfig):
    """Configuration of simulation output.

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


# -----------------------------------------------------------------------------
# Simulation
# -----------------------------------------------------------------------------
class SimulationConfig(FrozenConfig):
    """
    Complete simulation configuration.

    Contains execution parameters only.
    No biological network parameters belong here.
    """

    t_sim: float = Field(default=100.0, gt=0.0, description="simulated time (ms)")
    resolution: float = Field(default=0.1, gt=0.0, description="simulation time step (ms)")
    rng_seed: int = Field(default=42, description="seed of the random numbers")
    local_num_threads: int = Field(default=1, ge=1, description="threads per process")
    print_time: bool = Field(default=True, description="print the simulation progress")
    recording: RecordingConfig = Field(default=RecordingConfig(), description="what to record")
    output: OutputConfig = Field(default=OutputConfig(), description="where and what to save")