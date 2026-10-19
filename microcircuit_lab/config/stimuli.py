"""What ``stimuli.yaml`` may contain: targeted, time-limited stimuli.

To add a stimulus type: write its class here (a subclass of ``StimulusBase``
with its own ``type``), add it to ``StimulusConfig`` at the end of this file,
and create its device in ``NestBackend.create_stimuli``
(``backends/nest/backend.py``). See "Changing the core" in CONTRIBUTING.md.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field

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


class DcStimulusConfig(StimulusBase):
    """Constant-current pulse. Current is injected directly; no weight/delay."""

    type: Literal["dc"] = "dc"
    amplitude: float = Field(examples=[200.0], description="current (pA)")


class PoissonStimulusConfig(StimulusBase):
    """Homogeneous Poisson spike train, active for [start, stop)."""

    type: Literal["poisson"] = "poisson"
    rate: float = Field(ge=0.0, examples=[50.0], description="spike rate (spikes/s)")
    weight: WeightDistribution = Field(description="weight of each stimulus connection")
    delay: DelayDistribution = Field(description="delay of each stimulus connection")


class InhomogeneousPoissonStimulusConfig(StimulusBase):
    """Poisson spike train with a piecewise-constant rate profile."""

    type: Literal["inhomogeneous_poisson"] = "inhomogeneous_poisson"
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
    ``inhomogeneous_poisson`` device selected by its ``type`` field, with
    the fields of that type (above).
    """

    stimuli: list[StimulusConfig] = Field(
        default_factory=list, description="one entry per stimulus; `type` selects its fields"
    )
