"""
Simulation configuration models.

This module defines immutable configuration objects describing how a
simulation should be executed.

The parameters describe execution settings such as simulation time, random seeds,
recording options and output locations.
"""

from __future__ import annotations
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field


# -----------------------------------------------------------------------------
# Base class
# -----------------------------------------------------------------------------
class FrozenConfig(BaseModel):
    """Base class for immutable configuration models."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


# -----------------------------------------------------------------------------
# Recording
# -----------------------------------------------------------------------------
class RecordingConfig(FrozenConfig):
    """
    Configuration of recording devices.
    Individual simulator backends decide how these requests are implemented.
    """

    spike_recording: bool = True
    voltage_recording: bool = False
    voltage_interval: float = Field(default=1.0, gt=0.0)


# -----------------------------------------------------------------------------
# Output
# -----------------------------------------------------------------------------
class OutputConfig(FrozenConfig):
    """Configuration of simulation output."""

    output_dir: Path
    overwrite: bool = False
    save_metadata: bool = True
    save_config: bool = True


# -----------------------------------------------------------------------------
# Simulation
# -----------------------------------------------------------------------------
class SimulationConfig(FrozenConfig):
    """
    Complete simulation configuration.

    Contains execution parameters only.
    No biological network parameters belong here.
    """

    t_sim: float = Field(gt=0.0)
    resolution: float = Field(gt=0.0)
    rng_seed: int
    local_num_threads: int = Field(default=1, ge=1)
    print_time: bool = True
    recording: RecordingConfig = RecordingConfig()
    output: OutputConfig