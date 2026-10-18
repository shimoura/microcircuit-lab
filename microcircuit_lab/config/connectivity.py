"""What ``connectivity.yaml`` may contain: one row per projection.

``WeightDistribution`` and ``DelayDistribution`` are also used by background
inputs and stimuli.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from microcircuit_lab.config.base import FrozenConfig


class WeightDistribution(FrozenConfig):
    """
    Distribution describing synaptic weights.

    The interpretation of `mean` depends on `unit`, which is required --
    deliberately no default, so a config can't silently run with the
    wrong conversion just because a field was left out:

    - "PSP": biological post-synaptic potential amplitude (mV). Converted
      by prepare_network to a current amplitude, which only makes
      sense for a current-based LIF neuron with single-exponential
      synaptic currents; see network.units.convert_psp_to_psc for
      exactly what that requires from the target population's neuron
      parameters.
    - "PSC": post-synaptic current amplitude (pA), already in the form a
      current-based simulator backend consumes directly. Used as-is, no
      conversion.
    - "native": used exactly as given, with no interpretation at all.
      The right choice for a neuron model with no PSP/PSC conversion
      formula implemented -- e.g. a conductance-based model (nS weights)
      or anything else -- so adding a new neuron model never requires
      adding new conversion code, only picking the right unit.
    """

    mean: float = Field(description="amplitude; its meaning is set by `unit`")

    rel_std: float = Field(ge=0.0, description="standard deviation / |mean|")

    # To add a distribution: list it here (and in DelayDistribution below if it
    # applies to delays) and draw it in NestBackend.create_weight_spec /
    # create_delay_parameter (backends/nest/backend.py).
    distribution: Literal[
        "normal",
        "lognormal",
        "fixed",
    ] = Field(default="normal", description="normal | lognormal | fixed")

    unit: Literal[
        "PSC",
        "PSP",
        "native",
    ] = Field(description="PSP (mV, converted) | PSC (pA, as-is) | native (as-is)")


class DelayDistribution(FrozenConfig):
    """Distribution describing synaptic delays."""

    mean: float = Field(gt=0.0, description="mean delay (ms)")
    rel_std: float = Field(ge=0.0, description="standard deviation / mean")
    distribution: Literal["normal", "lognormal", "fixed"] = Field(
        default="normal", description="normal | lognormal | fixed"
    )
    minimum: float | None = Field(
        default=None,
        gt=0.0,
        description="smallest allowed delay (ms) of a drawn delay, never below half the "
        "simulation step; omit for half the simulation step",
    )


class ConnectionConfig(FrozenConfig):
    """Description of one projection between two populations."""

    source: str = Field(description="source population name")
    target: str = Field(description="target population name")
    n_synapses: int = Field(ge=0, description="total number of synapses in the projection")
    weight: WeightDistribution
    delay: DelayDistribution


class ConnectivityFile(FrozenConfig):
    """``connectivity.yaml``.

    Each row is a :class:`ConnectionConfig` -- already the on-disk shape:
    string ``source``/``target`` names, ``n_synapses`` (int >= 0), and a
    ``weight`` / ``delay`` distribution (see ``config/network.py`` for
    those fields). Omit a pair entirely rather than writing ``n_synapses: 0``.
    """

    connections: list[ConnectionConfig]
    bound_mode: Literal["redraw", "clip"] = Field(
        default="redraw",
        description="what to do with a drawn weight or delay outside its allowed "
        "range: 'redraw' draws again, 'clip' replaces it by the limit; applies to "
        "all weights and delays of the network, background inputs included",
    )
