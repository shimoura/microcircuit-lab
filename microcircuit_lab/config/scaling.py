"""What ``scaling.yaml`` may contain: the record of how a network was scaled.

A scaled network folder holds the scaled numbers themselves; ``scaling.yaml``
only says where they came from, and is never applied.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator

from microcircuit_lab.config.frozen_config import FrozenConfig


class ScalingRecord(FrozenConfig):
    """How a network was scaled, written by the function that scaled it: the
    core's :func:`microcircuit_lab.builder_tools.scaling.scale_network`, or a
    project's own, with its own ``parameters``. Nothing reads it to change a
    value: the files already hold the scaled ones."""

    scaled_from: str = Field(
        examples=["pd14"],
        description="the full-scale network this one was scaled from (or the builder command that makes it)",
    )
    scaled_with: str = Field(
        examples=["microcircuit_lab.builder_tools.scaling.scale_network"],
        description="the function that scaled it",
    )
    parameters: dict[str, Any] = Field(
        examples=[{"N_scaling": 0.1, "K_scaling": 0.1}],
        description="the arguments the function was given (its own, e.g. N_scaling and K_scaling)",
    )

    @model_validator(mode="before")
    @classmethod
    def _refuse_scaling_at_run_time(cls, data):
        if isinstance(data, dict) and "scaled_from" not in data:
            raise ValueError(
                "scaling.yaml no longer scales the network when it runs: the network folder holds the "
                "numbers that are simulated. Write a scaled folder with the builder "
                "(microcircuit-lab generate <model> --n-scaling ... --k-scaling ... --network-name ...) "
                "or with builder_tools.scale_network, and remove this scaling.yaml"
            )
        return data
