"""What ``background_inputs.yaml`` may contain: the always-on input of each population.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from microcircuit_lab.config.base import FrozenConfig
from microcircuit_lab.config.connectivity import DelayDistribution, WeightDistribution


class BackgroundInputConfig(FrozenConfig):
    """
    Always-on background Poisson input for a population.

    Distinct from `StimulusConfig`: this is the standing drive tied to
    `background_indegree`, subject to K-scaling and DC compensation
    (see network/scaling.py). `StimulusConfig` is for targeted,
    time-limited experimental perturbations instead.
    """

    rate: float = Field(
        ge=0.0, examples=[8.0], description="background Poisson rate per connection (spikes/s)"
    )
    weight: WeightDistribution = Field(description="weight of each background connection")
    delay: DelayDistribution = Field(description="delay of each background connection")


class BackgroundInputsFile(FrozenConfig):
    """``background_inputs.yaml`` -- one entry per population name.

    Each value is a :class:`BackgroundInputConfig` (``rate`` >= 0, plus a
    ``weight`` / ``delay`` with the same shape as in ``connectivity.yaml``).
    """

    background_inputs: dict[str, BackgroundInputConfig] = Field(
        description="one entry per population, keyed by its name; a population left out gets none",
    )
    background_mode: Literal["poisson", "dc"] = Field(
        default="poisson",
        description="'dc' replaces the Poisson drive network-wide with a "
        "constant current of the same mean",
    )
