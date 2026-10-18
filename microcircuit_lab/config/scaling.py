"""What ``scaling.yaml`` may contain: how to downscale the network.
"""

from __future__ import annotations

from pydantic import Field

from microcircuit_lab.config.base import FrozenConfig


class ScalingConfig(FrozenConfig):
    """
    Network scaling parameters.

    N_scaling:
        Multiplies the number of neurons.

    K_scaling:
        Multiplies the indegree / number of synapses.

    preserve_variance:
        Selects the weight-scaling law (see network.scaling.scale_weights).
        True (default): w -> w / sqrt(K_scaling) -- preserves input
        fluctuations, biases mean input. False: w -> w / K_scaling --
        preserves mean input directly, at the cost of fluctuations (no
        variance compensation is attempted in that case).

    preserve_mean_input:
        Master switch for whether prepare_network applies DC-current
        compensation for the mean-input bias sqrt scaling introduces.
        Only meaningful when preserve_variance is True -- under linear
        scaling there is no bias to compensate for.

    compensate_recurrent_input:
        True (default): the DC compensation also replaces the mean input
        lost from the recurrent connections, which needs the full-scale
        mean rate of every population in reference.full_mean_rates.
        False: it replaces only the lost background input. Ignored unless
        preserve_variance and preserve_mean_input are True.
    """

    # Scaling factors: default to 1.0 (no scaling) and gt(greater than)=0.0
    # to ensure positive values.
    N_scaling: float = Field(default=1.0, gt=0.0)
    K_scaling: float = Field(default=1.0, gt=0.0)

    preserve_mean_input: bool = True
    preserve_variance: bool = True
    compensate_recurrent_input: bool = True

    @property
    def is_scaled(self) -> bool:
        return (
            self.N_scaling != 1.0
            or self.K_scaling != 1.0
        )
