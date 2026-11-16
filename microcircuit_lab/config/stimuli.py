"""What ``stimuli.yaml`` may contain: targeted, time-limited stimuli.

To add a stimulus type: write its class here (a subclass of ``StimulusBase``
with its own ``type``), add it to ``StimulusConfig`` at the end of this file,
and create it in each backend's ``create_stimuli`` (``backends/nest/simulator.py``,
``backends/brian2/inputs.py``).
See "Changing the core" in https://github.com/shimoura/microcircuit-lab/blob/main/CONTRIBUTING.md#changing-the-core
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from microcircuit_lab.config.distributions import DelayDistribution, WeightDistribution
from microcircuit_lab.config.frozen_config import FrozenConfig


class StimulusBase(FrozenConfig):
    """
    Fields shared by every stimulus.

    A stimulus is applied to some populations during part of the run, exactly as
    configured and on top of the background input and the recurrent activity.
    Scaling does not change it. A ``poisson_background`` entry is the always-on
    input instead.
    """

    targets: list[str] = Field(
        min_length=1, examples=[["L4_E", "L4_I"]], description="population names to stimulate; one device, connected to every neuron of each"
    )
    start: float = Field(default=0.0, ge=0.0, description="when the stimulus starts (ms)")
    stop: float | None = Field(
        default=None,
        gt=0.0,
        examples=[600.0],
        description="when it stops (ms); omit to keep it on until the end",
    )

    @model_validator(mode="after")
    def _check_stop_after_start(self) -> StimulusBase:
        if self.stop is not None and self.stop <= self.start:
            raise ValueError(f"stop must be after start: got start={self.start}, stop={self.stop}")
        return self


class DcStimulusConfig(StimulusBase):
    """A constant current from ``start`` to ``stop``, which reaches the neurons ``delay`` later (no weight)."""

    type: Literal["dc"] = Field(default="dc", description="dc: a constant current")
    amplitude: float = Field(examples=[200.0], description="current (pA)")
    delay: DelayDistribution = Field(
        examples=[{"value": 1.0}],
        description="time from the stimulus to the neurons (ms), a fixed value: the current is on "
        "from start + delay to stop + delay",
    )

    @model_validator(mode="before")
    @classmethod
    def _ask_for_the_delay(cls, data):
        if isinstance(data, dict) and "delay" not in data:
            raise ValueError(
                "a dc stimulus needs its delay, the time from the stimulus to the neurons, e.g. "
                "delay: {value: 1.0} (so far it was not in the file: 1 ms on NEST, none on Brian2)"
            )
        return data

    @model_validator(mode="after")
    def _check_delay_is_fixed(self) -> DcStimulusConfig:
        if self.delay.distribution is not None:
            raise ValueError("a dc stimulus takes a fixed delay, e.g. delay: {value: 1.0}, not a distribution")
        return self


class PoissonStimulusConfig(StimulusBase):
    """Homogeneous Poisson spike train, active for [start, stop)."""

    type: Literal["poisson"] = Field(default="poisson", description="poisson: a Poisson spike train")
    rate: float = Field(ge=0.0, examples=[50.0], description="spike rate (spikes/s)")
    weight: WeightDistribution = Field(description="weight of each stimulus connection")
    delay: DelayDistribution = Field(description="delay of each stimulus connection")
    synapse: str | None = Field(
        default=None,
        examples=["depressing"],
        description="name of an entry in synapses.yaml; omit for the default synapse",
    )


class InhomogeneousPoissonStimulusConfig(StimulusBase):
    """Poisson spike train with a piecewise-constant rate profile."""

    type: Literal["inhomogeneous_poisson"] = Field(
        default="inhomogeneous_poisson",
        description="inhomogeneous_poisson: a Poisson spike train whose rate changes at given times",
    )
    rate_times: list[float] = Field(
        min_length=1, examples=[[200.0, 400.0]], description="when the rate changes (ms), increasing"
    )
    rate_values: list[float] = Field(
        min_length=1,
        examples=[[20.0, 0.0]],
        description="the rate from each of those times on (spikes/s), one per time",
    )
    weight: WeightDistribution = Field(description="weight of each stimulus connection")
    delay: DelayDistribution = Field(description="delay of each stimulus connection")
    synapse: str | None = Field(
        default=None,
        examples=["depressing"],
        description="name of an entry in synapses.yaml; omit for the default synapse",
    )

    @model_validator(mode="after")
    def _check_rate_profile(self) -> InhomogeneousPoissonStimulusConfig:
        times, values = self.rate_times, self.rate_values
        if len(times) != len(values):
            raise ValueError(f"rate_times and rate_values need the same length: got {len(times)} and {len(values)}")
        if any(later <= earlier for earlier, later in zip(times, times[1:])):
            raise ValueError(f"rate_times must increase: got {times}")
        if any(rate < 0 for rate in values):
            raise ValueError(f"rate_values must be 0 or more: got {values}")
        return self


# The "type" field selects which class a stimulus entry is checked against, so
# each type requires only its own fields. A new type is a new class in this union.
StimulusConfig = Annotated[
    DcStimulusConfig | PoissonStimulusConfig | InhomogeneousPoissonStimulusConfig,
    Field(discriminator="type"),
]


class StimuliFile(FrozenConfig):
    """``stimuli.yaml`` (optional; only read when ``network.yaml`` names it).

    Each entry is a :data:`StimulusConfig`: a ``dc``, ``poisson`` or
    ``inhomogeneous_poisson`` stimulus, chosen by its ``type`` field and with
    the fields of that type (above).
    """

    stimuli: list[StimulusConfig] = Field(
        default_factory=list, description="one entry per stimulus; `type` selects its fields"
    )


def check_times_on_time_step(stimuli: list[StimulusConfig], resolution: float) -> None:
    """
    Raise if a stimulus time (``start``, ``stop``, ``rate_times``) is not a
    multiple of the simulation time step: a simulator would either refuse it
    while building or round it, each in its own way.
    """
    for index, stimulus in enumerate(stimuli):
        times = {"start": [stimulus.start], "stop": [stimulus.stop]}
        times["rate_times"] = getattr(stimulus, "rate_times", [])

        for name, values in times.items():
            for time in values:
                if time is None:
                    continue
                steps = time / resolution
                if abs(steps - round(steps)) > 1e-6:
                    raise ValueError(
                        f"stimuli[{index}] ({stimulus.type}): {name} = {time} ms is not a "
                        f"multiple of the simulation time step (resolution: {resolution} ms)."
                    )
