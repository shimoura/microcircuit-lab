"""
Schema for the YAML files in a ``configs/network/<name>/`` directory --
and the field reference for anyone writing one by hand or from a generator.

One model per file, describing the config **exactly as it sits on disk**.
A field with no default is **required**; a field with ``Field(default=...)``
is **optional** and the default is shown. ``Field(gt=0)`` / ``ge=0.0`` etc.
are the value constraints. ``configs/network/toy/`` is the same schema as a
small *working* network to copy and edit.

Both entry points into the framework meet here:

* hand-writing the YAML: a mistyped or unknown field is rejected on load
  with a message that names the file and the field, instead of surfacing
  later as a confusing ``KeyError``;
* writing a generator: whatever code produces the files, its output only
  has to satisfy :class:`NetworkDirectory` (see
  :func:`microcircuit_lab.io.network_validation.validate_network_config`).

These are distinct from the models in :mod:`microcircuit_lab.config.network`,
which describe the network *after* the files are read and cross-references
resolved (a population there holds a resolved :class:`NeuronConfig`; here
it holds a neuron *name*). The leaf models already in on-disk shape --
:class:`ConnectionConfig`, :class:`~microcircuit_lab.config.network.WeightDistribution`,
:class:`~microcircuit_lab.config.network.DelayDistribution`,
:class:`BackgroundInputConfig`, :class:`ScalingConfig`, :class:`ReferenceConfig`,
:data:`StimulusConfig` -- are reused directly; see ``config/network.py`` for
their fields.

``extra="forbid"`` (from :class:`FrozenConfig`) makes an unknown key an
error rather than a silently ignored no-op. The one exception is a neuron's
``parameters`` block, which stays open on purpose: neuron models differ in
which parameters they accept, and the simulator backend is the authority on
those names (see :class:`NeuronParams`).
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from microcircuit_lab.config.base import FrozenConfig
from microcircuit_lab.config.network import (
    BackgroundInputConfig,
    ConnectionConfig,
    NeuronParams,
    ReferenceConfig,
    ScalingConfig,
    StimulusConfig,
)


class NetworkManifest(FrozenConfig):
    """``network.yaml`` -- maps each part of the network to its file name."""

    populations: str = Field(description="file holding the populations list")
    neurons: str = Field(description="file holding the neuron definitions")
    connectivity: str = Field(description="file holding the connection list")
    background_inputs: str = Field(description="file holding the background-input entries")
    scaling: str = Field(description="file holding the scaling parameters")
    reference: str = Field(description="file holding the reference rates")
    stimuli: str | None = Field(
        default=None,
        description="file holding targeted stimuli; omit the key for none",
    )


class PopulationEntry(FrozenConfig):
    """One row of ``populations.yaml``."""

    name: str = Field(
        description="unique population name; referenced by connectivity, "
        "background_inputs, stimuli and reference"
    )
    size: int = Field(gt=0, description="number of neurons")
    neuron: str = Field(description="name of an entry in neurons.yaml")
    V0_mean: float = Field(description="mean initial membrane potential (mV)")
    V0_std: float = Field(ge=0.0, description="standard deviation of the initial potential (mV)")
    background_indegree: float = Field(
        default=0.0,
        ge=0.0,
        description="background-input connections per neuron; multiplies the "
        "rate in background_inputs.yaml",
    )


class PopulationsFile(FrozenConfig):
    """``populations.yaml``."""

    populations: list[PopulationEntry]


class NeuronEntry(FrozenConfig):
    """One entry of ``neurons.yaml`` (the file key is the neuron's name)."""

    model: str = Field(description="the simulator's neuron model name, e.g. iaf_psc_exp")
    parameters: NeuronParams = Field(
        description="parameters passed to that model as-is; keys are "
        "model-specific and the backend validates them (I_e defaults to 0.0)"
    )
    psp_conversion_aliases: dict[str, str] = Field(
        default_factory=dict,
        description="only for `unit: PSP` connections whose neuron names "
        "C_m/tau_m/tau_syn_ex/tau_syn_in differently, e.g. {C_m: cm}",
    )


class NeuronsFile(FrozenConfig):
    """``neurons.yaml``."""

    neurons: dict[str, NeuronEntry]


class ConnectivityFile(FrozenConfig):
    """``connectivity.yaml``.

    Each row is a :class:`ConnectionConfig` -- already the on-disk shape:
    string ``source``/``target`` names, ``n_synapses`` (int >= 0), and a
    ``weight`` / ``delay`` distribution (see ``config/network.py`` for
    those fields). Omit a pair entirely rather than writing ``n_synapses: 0``.
    """

    connections: list[ConnectionConfig]


class BackgroundInputsFile(FrozenConfig):
    """``background_inputs.yaml`` -- one entry per population name.

    Each value is a :class:`BackgroundInputConfig` (``rate`` >= 0, plus a
    ``weight`` / ``delay`` with the same shape as in ``connectivity.yaml``).
    """

    background_inputs: dict[str, BackgroundInputConfig]
    background_mode: Literal["poisson", "dc"] = Field(
        default="poisson",
        description="'dc' replaces the Poisson drive network-wide with a "
        "constant current of the same mean",
    )


class StimuliFile(FrozenConfig):
    """``stimuli.yaml`` (optional; only read when ``network.yaml`` names it).

    Each entry is a :data:`StimulusConfig` -- a ``dc`` / ``poisson`` /
    ``inhomogeneous_poisson`` device selected by its ``type`` field; see
    ``config/network.py`` for the per-type fields.
    """

    stimuli: list[StimulusConfig] = Field(default_factory=list)


class NetworkDirectory(FrozenConfig):
    """The whole ``configs/network/<name>/`` directory, validated at once.

    Reading the files into this single object (rather than validating each
    in isolation) is what lets a message point at both the file and the
    field: ``populations.populations.0.size`` reads as "the ``size`` of
    the first row of ``populations.yaml``".
    """

    manifest: NetworkManifest
    populations: PopulationsFile
    neurons: NeuronsFile
    connectivity: ConnectivityFile
    background_inputs: BackgroundInputsFile
    scaling: ScalingConfig
    reference: ReferenceConfig
    stimuli: StimuliFile = Field(default_factory=StimuliFile)
