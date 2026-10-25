"""What ``stimuli.yaml`` may contain: targeted, time-limited stimuli.

To add a stimulus type: write its class here (a subclass of ``StimulusBase``
with its own ``type``), add it to ``StimulusConfig`` at the end of this file,
and create it in each backend's ``create_stimuli`` (``backends/<name>/simulator.py``).
See "Changing the core" in CONTRIBUTING.md.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from microcircuit_lab.config.connectivity import DelayDistribution, WeightDistribution
from microcircuit_lab.config.frozen_config import FrozenConfig


class StimulusBase(FrozenConfig):
    """
    Fields shared by every stimulus.

    A stimulus is applied to some populations during part of the run, exactly as
    configured and on top of the background input and the recurrent activity.
    Scaling does not change it. A ``background_inputs`` entry is the always-on
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


class DcStimulusConfig(StimulusBase):
    """A constant current from ``start`` to ``stop``, injected directly (no weight or delay)."""

    type: Literal["dc"] = "dc"
    amplitude: float = Field(examples=[200.0], description="current (pA)")


class PoissonStimulusConfig(StimulusBase):
    """Homogeneous Poisson spike train, active for [start, stop)."""

    type: Literal["poisson"] = "poisson"
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
    synapse: str | None = Field(
        default=None,
        examples=["depressing"],
        description="name of an entry in synapses.yaml; omit for the default synapse",
    )


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
