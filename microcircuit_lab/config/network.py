"""
Network configuration models.

This module defines the immutable configuration objects describing the
biological network. They are pure data containers and must not contain
simulation logic or simulator-specific code.

These models are intended to be populated from YAML files and consumed by
NetworkPreprocessor to derive all quantities required by the simulator backend.
"""

from __future__ import annotations
from typing import Annotated, Literal, Union
from pydantic import BaseModel, ConfigDict, Field, model_validator


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
# Background input
# -----------------------------------------------------------------------------
class BackgroundInputConfig(FrozenConfig):
    """
    Always-on background Poisson input for a population.

    Distinct from `StimulusConfig`: this is the standing drive tied to
    `background_indegree`, subject to K-scaling and DC compensation
    (see network/scaling.py). `StimulusConfig` is for targeted,
    time-limited experimental perturbations instead.
    """

    rate: float = Field(ge=0.0)
    weight: WeightDistribution
    delay: DelayDistribution


# -----------------------------------------------------------------------------
# Stimulation
# -----------------------------------------------------------------------------
class StimulusBase(FrozenConfig):
    """
    Fields shared by every targeted, time-limited stimulation device.

    Distinct from `background_inputs` (the always-on background drive tied
    to `background_indegree`, subject to K-scaling and DC compensation):
    stimuli are not touched by network scaling and are applied exactly
    as configured, on top of whatever background drive and recurrent
    activity is already there. Intended for experimental perturbations
    (a current pulse, a burst of input for part of a run, ...).

    targets:
        Population names this device is connected to (all-to-all, one
        device shared by all targets).

    start / stop:
        Window during which the device is active, in ms. `stop=None`
        means "until the end of the simulation".
    """

    targets: list[str] = Field(min_length=1)

    start: float = Field(default=0.0, ge=0.0)
    stop: float | None = Field(default=None, gt=0.0)

    @model_validator(mode="after")
    def _check_window(self) -> "StimulusBase":
        if self.stop is not None and self.stop <= self.start:
            raise ValueError(f"stop ({self.stop}) must be greater than start ({self.start}).")
        return self


class DcStimulusConfig(StimulusBase):
    """Constant-current pulse. Current is injected directly -- no weight/delay."""

    type: Literal["dc"] = "dc"
    amplitude: float


class PoissonStimulusConfig(StimulusBase):
    """Homogeneous Poisson spike train, active for [start, stop)."""

    type: Literal["poisson"] = "poisson"
    rate: float = Field(ge=0.0)
    weight: WeightDistribution
    delay: DelayDistribution


class InhomogeneousPoissonStimulusConfig(StimulusBase):
    """Poisson spike train with a piecewise-constant rate profile."""

    type: Literal["inhomogeneous_poisson"] = "inhomogeneous_poisson"
    rate_times: list[float] = Field(min_length=1, description="ms, strictly increasing")
    rate_values: list[float] = Field(min_length=1, description="spikes/s, same length as rate_times")
    weight: WeightDistribution
    delay: DelayDistribution

    @model_validator(mode="after")
    def _check_rate_profile(self) -> "InhomogeneousPoissonStimulusConfig":
        if len(self.rate_times) != len(self.rate_values):
            raise ValueError("'rate_times' and 'rate_values' must be the same length.")
        if any(a >= b for a, b in zip(self.rate_times, self.rate_times[1:])):
            raise ValueError("'rate_times' must be strictly increasing.")
        return self


# Discriminated union: the `type` field selects which subtype a YAML/dict
# stimulus entry is validated against, so each type only ever requires the
# fields it actually uses -- adding a new stimulus type means adding a new
# subtype here, not another branch in a shared validator.
StimulusConfig = Annotated[
    Union[DcStimulusConfig, PoissonStimulusConfig, InhomogeneousPoissonStimulusConfig],
    Field(discriminator="type"),
]


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

    preserve_variance:
        Selects the weight-scaling law (see network.scaling.scale_weights).
        True (default): w -> w / sqrt(K_scaling) -- preserves input
        fluctuations, biases mean input. False: w -> w / K_scaling --
        preserves mean input directly, at the cost of fluctuations (no
        variance compensation is attempted in that case).

    preserve_mean_input:
        Master switch for whether NetworkPreprocessor applies DC-current
        compensation for the mean-input bias sqrt scaling introduces.
        Only meaningful when preserve_variance is True -- under linear
        scaling there is no bias to compensate for.
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

    background_inputs: dict[str, BackgroundInputConfig]
    stimuli: list[StimulusConfig] = Field(default_factory=list)
    scaling: ScalingConfig

    reference: ReferenceConfig | None = None

    @model_validator(mode="after")
    def _check_stimulus_targets_exist(self) -> "NetworkConfig":
        for stimulus in self.stimuli:
            unknown = [t for t in stimulus.targets if t not in self.populations]
            if unknown:
                raise ValueError(
                    f"Stimulus of type {stimulus.type!r} targets unknown "
                    f"population(s): {unknown}."
                )
        return self
