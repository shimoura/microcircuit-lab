"""What ``reference.yaml`` may contain: published reference values.
"""

from __future__ import annotations

from pydantic import Field

from microcircuit_lab.config.base import FrozenConfig


class ReferenceConfig(FrozenConfig):
    """
    Reference quantities from published benchmark models.

    These values are not intrinsic properties of the biological
    network itself, but are used to reproduce or validate
    published reference implementations.
    """

    full_mean_rates: dict[str, float] = Field(
        default_factory=dict,
        examples=[{"L23_E": 0.97, "L23_I": 2.9}],
        description="mean rate (spikes/s) of each population at full scale; needed when a "
        "scaled network compensates the recurrent input, and shown next to the rates of a run",
    )
