"""
Network configuration models.

This module defines the immutable configuration objects describing the
biological network. They are pure data containers and must not contain
simulation logic or simulator-specific code.

These models are intended to be populated from YAML files and consumed by
NetworkPreprocessor to derive all quantities required by the simulator backend.
"""

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


# -----------------------------------------------------------------------------
# Base class
# -----------------------------------------------------------------------------
class FrozenConfig(BaseModel):
    """Base class for immutable configuration models."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


# -----------------------------------------------------------------------------
# Neuron parameters
# -----------------------------------------------------------------------------
class NeuronParams(FrozenConfig):
    """
    Parameters for a neuron model.

    The fields intentionally mirror the corresponding simulator parameters
    (e.g. NEST's iaf_psc_exp or aeif_cond_exp) while remaining simulator
    independent.
    """

    C_m: float
    tau_m: float
    tau_syn_ex: float
    tau_syn_in: float
    E_L: float
    V_reset: float
    V_th: float
    t_ref: float
    I_e: float = 0.0


# -----------------------------------------------------------------------------
# Neuron model
# -----------------------------------------------------------------------------
class NeuronConfig(FrozenConfig):
    """
    Configuration for a neuron model.
    This is a pure data container for the parameters of a neuron model.
    """

    name: str
    model: str
    parameters: NeuronParams


# -----------------------------------------------------------------------------
# Population
# -----------------------------------------------------------------------------
class PopulationConfig(FrozenConfig):
    """Description of one neuronal population."""

    name: str
    size: int = Field(gt=0)

    neuron: NeuronConfig

    V0_mean: float
    V0_std: float = Field(ge=0.0)
    background_indegree: float = Field(default=0.0, ge=0.0)


# -----------------------------------------------------------------------------
# Synaptic distributions
# -----------------------------------------------------------------------------
class WeightDistribution(FrozenConfig):
    """
    Distribution describing synaptic weights.

    The interpretation of `mean` depends on `unit`, which is required --
    deliberately no default, so a config can't silently run with the
    wrong conversion just because a field was left out:

    - "PSP": biological post-synaptic potential amplitude (mV). Converted
      to a simulator-specific quantity by NetworkPreprocessor, which
      requires a formula for the target neuron model (currently only
      implemented for `iaf_psc_exp`; see network.parameters).
    - "PSC": post-synaptic current amplitude (pA), already in the form a
      current-based simulator backend consumes directly. Used as-is, no
      conversion.
    - "native": used exactly as given, with no interpretation at all.
      The right choice for a neuron model with no PSP/PSC conversion
      formula implemented -- e.g. a conductance-based model (nS weights)
      or anything else -- so adding a new neuron model never requires
      adding new conversion code, only picking the right unit.
    """

    mean: float

    rel_std: float = Field(ge=0.0)

    distribution: Literal[
        "normal",
        "lognormal",
        "fixed",
    ] = "normal"

    unit: Literal[
        "PSC",
        "PSP",
        "native",
    ]


class DelayDistribution(FrozenConfig):
    """Distribution describing synaptic delays."""

    mean: float = Field(gt=0.0)
    rel_std: float = Field(ge=0.0)
    distribution: Literal["normal", "lognormal", "fixed"] = "normal"


# -----------------------------------------------------------------------------
# Connectivity
# -----------------------------------------------------------------------------
class ConnectionConfig(FrozenConfig):
    """Description of one projection between two populations."""

    source: str
    target: str
    n_synapses: int = Field(ge=0)
    weight: WeightDistribution
    delay: DelayDistribution


# -----------------------------------------------------------------------------
# External input
# -----------------------------------------------------------------------------
class PoissonInputConfig(FrozenConfig):
    """Background Poisson input for a population."""

    rate: float = Field(ge=0.0)
    weight: WeightDistribution
    delay: DelayDistribution


# -----------------------------------------------------------------------------
# Scaling
# -----------------------------------------------------------------------------
class ScalingConfig(FrozenConfig):
    """
    Network scaling parameters.

    N_scaling:
        Multiplies the number of neurons.

    K_scaling:
        Multiplies the indegree / number of synapses.

    preserve_mean_input:
        Whether scaling should preserve the mean synaptic input.

    preserve_variance:
        Whether scaling should preserve input variance.
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


# -----------------------------------------------------------------------------
# Reference data
# -----------------------------------------------------------------------------


class ReferenceConfig(FrozenConfig):
    """
    Reference quantities from published benchmark models.

    These values are not intrinsic properties of the biological
    network itself, but are used to reproduce or validate
    published reference implementations.
    """

    full_mean_rates: dict[str, float] = Field(default_factory=dict)


# -----------------------------------------------------------------------------
# Network
# -----------------------------------------------------------------------------
class NetworkConfig(FrozenConfig):
    """
    Complete biological network description.

    This object is the single source of truth describing the network model.
    It is assembled from the YAML files under configs/network/.
    """

    populations: dict[str, PopulationConfig]
    connections: list[ConnectionConfig]

    inputs: dict[str, PoissonInputConfig]
    scaling: ScalingConfig

    reference: ReferenceConfig | None = None
