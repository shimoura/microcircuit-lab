"""What the simulation file may contain: run time, seeds, backend, recording and output."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from microcircuit_lab.config.frozen_config import FrozenConfig

#: Registered backend names. Adding a backend means adding it here and to
#: get_backend(), read_saved_spikes() and read_saved_variable() in backends/__init__.py. See "A simulator"
#: in CONTRIBUTING.md.
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


class VariableRecording(FrozenConfig):
    """One neuron variable to record: how often, and from which neurons."""

    interval: float = Field(
        default=1.0, gt=0.0, description="time between two samples (ms)"
    )
    sample_size: int | None = Field(
        default=None,
        ge=1,
        examples=[5],
        description="neurons per population to record, the first ones; null records all",
    )
    populations: list[str] | None = Field(
        default=None,
        min_length=1,
        examples=[["E", "I"]],
        description="names of the populations to record (at least one); omit it to record all",
    )


class RecordingConfig(FrozenConfig):
    """What to record. The backend decides how."""

    spike_recording: bool = Field(default=True, description="record the spikes of every neuron")
    variables: dict[str, VariableRecording] = Field(
        default={},
        examples=[{"V_m": {"interval": 1.0, "sample_size": 5}}],
        description="neuron variables to record, keyed by the name the simulator gives them "
        "(V_m, or the synaptic input I_syn_ex / I_syn_in or g_ex / g_in, depending on the "
        "model); none by default. The simulator reports a name the model does not have",
    )

    @model_validator(mode="before")
    @classmethod
    def _refuse_voltage_fields(cls, data):
        removed = [key for key in ("voltage_recording", "voltage_interval", "voltage_sample_size")
                   if isinstance(data, dict) and key in data]
        if removed:
            raise ValueError(
                f"{', '.join(removed)} {'was' if len(removed) == 1 else 'were'} removed: record V_m with "
                "`variables: {V_m: {interval: 1.0, sample_size: 5}}` "
                "(any recordable variable of the model works the same way)"
            )
        return data

    def recorded_populations(self, variable: str, network_populations) -> list[str]:
        """
        The names of the populations whose ``variable`` is recorded, in the
        network's order. Raises if ``populations`` names one the network lacks.
        """

        names = self.variables[variable].populations
        if names is None:
            return list(network_populations)
        unknown = [name for name in names if name not in network_populations]
        if unknown:
            raise ValueError(
                f"recording.variables[{variable!r}].populations names unknown population(s): {unknown}."
            )
        return [name for name in network_populations if name in names]


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
        description="write config.yaml (the network and the simulation settings); needed to re-plot the run",
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