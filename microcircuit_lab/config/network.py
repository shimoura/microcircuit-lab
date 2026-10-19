"""The whole network: ``network.yaml`` and the files it names, together.

``NetworkDirectory`` is the folder as written on disk, validated at once so an
error names the file and the field. ``NetworkConfig`` is the network after
reading, the single description every later step uses (preparing it for the
simulation, the simulator backend, the analysis).
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from microcircuit_lab.config.background_inputs import BackgroundInputConfig, BackgroundInputsFile
from microcircuit_lab.config.base import FrozenConfig
from microcircuit_lab.config.connectivity import ConnectionConfig, ConnectivityFile
from microcircuit_lab.config.neurons import NeuronsFile
from microcircuit_lab.config.populations import PopulationConfig, PopulationsFile
from microcircuit_lab.config.reference import ReferenceConfig
from microcircuit_lab.config.scaling import ScalingConfig
from microcircuit_lab.config.stimuli import StimuliFile, StimulusConfig


class NetworkManifest(FrozenConfig):
    """``network.yaml`` -- maps each part of the network to its file name."""

    populations: str = Field(examples=["populations.yaml"], description="file holding the populations list")
    neurons: str = Field(examples=["neurons.yaml"], description="file holding the neuron definitions")
    connectivity: str = Field(examples=["connectivity.yaml"], description="file holding the connection list")
    background_inputs: str = Field(
        examples=["background_inputs.yaml"],
        description="file holding the background-input entries"
    )
    scaling: str = Field(examples=["scaling.yaml"], description="file holding the scaling parameters")
    reference: str = Field(examples=["reference.yaml"], description="file holding the reference rates")
    stimuli: str | None = Field(
        default=None,
        examples=["stimuli.yaml"],
        description="file holding targeted stimuli; omit the key for none",
    )


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
        prepare_network (step _replace_background_by_dc)); no Poisson
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

    @model_validator(mode="after")
    def _check_one_connection_per_pair(self) -> "NetworkConfig":
        # The scaling compensation keeps one number per (source, target), so a
        # second entry for the same pair would be simulated but not compensated.
        pairs = [(c.source, c.target) for c in self.connections]
        repeated = sorted({pair for pair in pairs if pairs.count(pair) > 1})
        if repeated:
            raise ValueError(
                f"connectivity.yaml has more than one entry for (source, target) {repeated}. "
                "Each pair takes one entry: several synapse models, receptors or connection "
                "rules for the same pair are not supported yet."
            )
        return self
