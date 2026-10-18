"""What ``stimuli.yaml`` may contain: targeted, time-limited stimuli.

To add a stimulus type: write its class here (a subclass of ``StimulusBase``
with its own ``type``), add it to ``StimulusConfig`` at the end of this file,
and create its device in ``NestBackend.create_stimuli``
(``backends/nest/backend.py``). See "Changing the core" in CONTRIBUTING.md.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field, model_validator

from microcircuit_lab.config.base import FrozenConfig
from microcircuit_lab.config.connectivity import DelayDistribution, WeightDistribution


class StimulusBase(FrozenConfig):
    """
    Fields shared by every targeted, time-limited stimulation device.

    Distinct from `background_inputs` (the always-on background drive tied
    to `background_indegree`, subject to K-scaling and DC compensation):
    stimuli are not touched by network scaling and are applied exactly
    as configured, on top of whatever background drive and recurrent
    activity is already there. Intended for experimental perturbations
    (a current pulse, a burst of input for part of a run, ...).

    targets:
        Population names this device is connected to (all-to-all, one
        device shared by all targets).

    start / stop:
        Window during which the device is active, in ms. `stop=None`
        means "until the end of the simulation".
    """

    targets: list[str] = Field(min_length=1)

    start: float = Field(default=0.0, ge=0.0)
    stop: float | None = Field(default=None, gt=0.0)

    @model_validator(mode="after")
    def _check_window(self) -> "StimulusBase":
        if self.stop is not None and self.stop <= self.start:
            raise ValueError(f"stop ({self.stop}) must be greater than start ({self.start}).")
        return self


class DcStimulusConfig(StimulusBase):
    """Constant-current pulse. Current is injected directly; no weight/delay."""

    type: Literal["dc"] = "dc"
    amplitude: float


class PoissonStimulusConfig(StimulusBase):
    """Homogeneous Poisson spike train, active for [start, stop)."""

    type: Literal["poisson"] = "poisson"
    rate: float = Field(ge=0.0)
    weight: WeightDistribution
    delay: DelayDistribution


class InhomogeneousPoissonStimulusConfig(StimulusBase):
    """Poisson spike train with a piecewise-constant rate profile."""

    type: Literal["inhomogeneous_poisson"] = "inhomogeneous_poisson"
    rate_times: list[float] = Field(min_length=1, description="ms, strictly increasing")
    rate_values: list[float] = Field(min_length=1, description="spikes/s, same length as rate_times")
    weight: WeightDistribution
    delay: DelayDistribution

    @model_validator(mode="after")
    def _check_rate_profile(self) -> "InhomogeneousPoissonStimulusConfig":
        if len(self.rate_times) != len(self.rate_values):
            raise ValueError("'rate_times' and 'rate_values' must be the same length.")
        if any(a >= b for a, b in zip(self.rate_times, self.rate_times[1:])):
            raise ValueError("'rate_times' must be strictly increasing.")
        return self


# Discriminated union: the `type` field selects which subtype a YAML/dict
# stimulus entry is validated against, so each type only ever requires the
# fields it actually uses. Adding a new stimulus type means adding a new
# subtype here, not another branch in a shared validator.
StimulusConfig = Annotated[
    Union[DcStimulusConfig, PoissonStimulusConfig, InhomogeneousPoissonStimulusConfig],
    Field(discriminator="type"),
]


class StimuliFile(FrozenConfig):
    """``stimuli.yaml`` (optional; only read when ``network.yaml`` names it).

    Each entry is a :data:`StimulusConfig` -- a ``dc`` / ``poisson`` /
    ``inhomogeneous_poisson`` device selected by its ``type`` field; see
    ``config/network.py`` for the per-type fields.
    """

    stimuli: list[StimulusConfig] = Field(default_factory=list)
