"""Shared base class for configuration models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class FrozenConfig(BaseModel):
    """Base class for immutable configuration models."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )
