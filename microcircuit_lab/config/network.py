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

from microcircuit_lab.config.base import FrozenConfig

# -----------------------------------------------------------------------------
# Neuron parameters
# -----------------------------------------------------------------------------
class NeuronParams(BaseModel):
    """
    Parameters for a neuron model, passed through to the simulator backend
    as-is.

    Deliberately open-ended rather than a fixed field list: neuron models
    differ in what they accept (a current-based integrate-and-fire model,
    a conductance-based one, an adaptive-exponential one, ...), so
    hard-coding one parameter set here would only ever fit a subset of
    them. Whatever keys you supply (besides `I_e`, see below) are set on
    the simulator-side neuron exactly as given. The simulator backend is
    the source of truth for which names a given model accepts, and it is
    the one that raises an error if given a name it doesn't recognize.
    This layer stays simulator-independent and does not duplicate that
    check.

    `I_e` (constant input current, pA) is the one field this package reads
    back directly, since DC-compensation (see network/preprocessing.py)
    adds to it when scaling the network. It's declared explicitly here and
    defaults to 0.0, since a constant input current at zero is the common
    starting point across point-neuron models generally.

    Values must be numeric; anything else (a string, a list, ...) is
    rejected here rather than surfacing as a confusing simulator-side
    error.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    I_e: float = 0.0

    @model_validator(mode="after")
    def _check_extra_params_are_numeric(self) -> "NeuronParams":
        non_numeric = {
            key: value
            for key, value in (self.__pydantic_extra__ or {}).items()
            if not isinstance(value, (int, float))
        }
        if non_numeric:
            raise ValueError(
                f"Neuron parameters must be numeric, got non-numeric values: {non_numeric!r}."
            )
        return self

    def require(self, *names: str) -> dict[str, float]:
        """
        Return the named parameters, or raise a clear error if any weren't
        provided.

        Parameters are open-ended here, so this is the only way for code
        that needs specific parameters by name (e.g. a PSP-to-PSC
        conversion formula tied to one neuron model) to know whether what
        it needs is actually present.
        """

        values = self.model_dump()
        missing = [name for name in names if name not in values]
        if missing:
            raise KeyError(f"Missing neuron parameters: {missing}.")
        return {name: values[name] for name in names}


# -----------------------------------------------------------------------------
# Neuron model
# -----------------------------------------------------------------------------
class NeuronConfig(FrozenConfig):
    """
    Configuration for a neuron model.
    This is a pure data container for the parameters of a neuron model.

    psp_conversion_aliases:
        Only relevant to connections that use ``unit: PSP``. Maps a
        canonical name the conversion needs ("C_m", "tau_m",
        "tau_syn_ex", "tau_syn_in") to whatever `parameters` actually
        calls it, for a model that names them differently (e.g. a
        NESTML model with its own naming convention). Empty by default,
        meaning `parameters` already uses those names directly (NEST's
        iaf_psc_exp and its usual variants). See
        network.synapses.convert_psp_to_psc.
    """

    name: str
    model: str
    parameters: NeuronParams
    psp_conversion_aliases: dict[str, str] = Field(default_factory=dict)


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
      by NetworkPreprocessor to a current amplitude, which only makes
      sense for a current-based LIF neuron with single-exponential
      synaptic currents; see network.synapses.convert_psp_to_psc for
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
        description="smallest allowed delay (ms); omit for half the simulation step",
    )


# -----------------------------------------------------------------------------
# Connectivity
# -----------------------------------------------------------------------------
class ConnectionConfig(FrozenConfig):
    """Description of one projection between two populations."""

    source: str = Field(description="source population name")
    target: str = Field(description="target population name")
    n_synapses: int = Field(ge=0, description="total number of synapses in the projection")
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

    rate: float = Field(ge=0.0, description="background Poisson rate per connection (spikes/s)")
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
    """Constant-current pulse. Current is injected directly; no weight/delay."""

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
# fields it actually uses. Adding a new stimulus type means adding a new
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

    background_mode:
        "poisson" (default): each population's background_inputs entry
        drives it through an independent Poisson generator, as usual.
        "dc": replaces that Poisson drive network-wide with a constant
        current of the same mean, per Potjans & Diesmann (2014)'s
        comparison of Poisson vs. DC background input (their Fig. 5).
        The `background_inputs` rate/weight/delay are still the source
        of truth for computing that mean (see
        NetworkPreprocessor._apply_background_dc_current); no Poisson
        generator is created in this mode.

    bound_mode:
        What to do with a drawn weight or delay that falls outside its
        allowed range (a weight of the wrong sign, a delay below its
        minimum). "redraw" (default): draw again until the value is
        allowed. "clip": replace the value by the limit, as the HuMAM
        model does. Applies to all weights and delays of the network.
    """

    populations: dict[str, PopulationConfig]
    connections: list[ConnectionConfig]

    background_inputs: dict[str, BackgroundInputConfig]
    background_mode: Literal["poisson", "dc"] = "poisson"
    bound_mode: Literal["redraw", "clip"] = "redraw"
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
