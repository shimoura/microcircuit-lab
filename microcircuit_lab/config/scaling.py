"""What ``scaling.yaml`` may contain: how to downscale the network."""

from __future__ import annotations

from pydantic import Field

from microcircuit_lab.config.base import FrozenConfig


class ScalingConfig(FrozenConfig):
    """How to downscale the network; the formulas are in ``network/scaling.py``.

    ``preserve_mean_input`` matters only when ``preserve_variance`` is true
    (linear weight scaling leaves no mean to restore), and
    ``compensate_recurrent_input`` only when both are true.
    """

    # Both factors default to 1.0 (no scaling) and must be greater than 0.
    N_scaling: float = Field(default=1.0, gt=0.0, description="multiplies the number of neurons")
    K_scaling: float = Field(
        default=1.0, gt=0.0, description="multiplies the indegrees (synapses per neuron)"
    )
    preserve_mean_input: bool = Field(
        default=True, description="add a DC current that restores the mean input lost by scaling"
    )
    preserve_variance: bool = Field(
        default=True,
        description="true: weights / sqrt(K_scaling), keeps the fluctuations; "
        "false: weights / K_scaling, keeps the mean and needs no DC current",
    )
    compensate_recurrent_input: bool = Field(
        default=True,
        description="the DC current also replaces the lost recurrent input (needs "
        "reference.full_mean_rates); false: only the lost background input",
    )

    @property
    def is_scaled(self) -> bool:
        return (
            self.N_scaling != 1.0
            or self.K_scaling != 1.0
        )
