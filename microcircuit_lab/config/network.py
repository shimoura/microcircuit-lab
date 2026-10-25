"""The whole network: ``network.yaml`` and the files it names, together.

``NetworkDirectory`` is the folder as written on disk, validated at once so an
error names the file and the field. ``NetworkConfig`` is the network after
reading. Preparing it for the simulation, the simulator backend and the
analysis all use it.
"""

from __future__ import annotations

from typing import Annotated, Literal

import numpy as np
from pydantic import (
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    model_validator,
)

from microcircuit_lab.config.background_inputs import (
    BackgroundInputConfig,
    BackgroundInputsFile,
)
from microcircuit_lab.config.connection_table import (
    ConnectionTable,
    to_connection_table,
)
from microcircuit_lab.config.connectivity import SHARED_DISTRIBUTIONS, ConnectivityFile
from microcircuit_lab.config.frozen_config import FrozenConfig
from microcircuit_lab.config.neurons import NeuronsFile
from microcircuit_lab.config.populations import PopulationConfig, PopulationsFile
from microcircuit_lab.config.reference import ReferenceConfig
from microcircuit_lab.config.scaling import ScalingConfig
from microcircuit_lab.config.stimuli import (
    DcStimulusConfig,
    StimuliFile,
    StimulusConfig,
)
from microcircuit_lab.config.synapses import SynapseEntry, SynapsesFile


class NetworkManifest(FrozenConfig):
    """``network.yaml``: maps each part of the network to its file name."""

    populations: str = Field(examples=["populations.yaml"], description="file holding the populations list")
    neurons: str = Field(examples=["neurons.yaml"], description="file holding the neuron definitions")
    connectivity: str = Field(examples=["connectivity.yaml"], description="file holding the connection list")
    background_inputs: str = Field(
        examples=["background_inputs.yaml"],
        description="file holding the background-input entries"
    )
    scaling: str | None = Field(
        default=None,
        examples=["scaling.yaml"],
        description="file holding the scaling parameters; omit the key to run the network "
        "at full scale",
    )
    reference: str | None = Field(
        default=None,
        examples=["reference.yaml"],
        description="file holding the reference rates; omit the key for none",
    )
    stimuli: str | None = Field(
        default=None,
        examples=["stimuli.yaml"],
        description="file holding targeted stimuli; omit the key for none",
    )
    synapses: str | None = Field(
        default=None,
        examples=["synapses.yaml"],
        description="file holding the synapse definitions; omit the key to use the "
        "default synapse everywhere",
    )


class NetworkDirectory(FrozenConfig):
    """The whole ``configs/network/<name>/`` directory, validated at once.

    Reading the files into this single object (rather than validating each
    in isolation) is what lets a message point at both the file and the
    field: ``populations.populations.0.size`` reads as "the ``size`` of
    the first row of ``populations.yaml``".
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    manifest: NetworkManifest
    populations: PopulationsFile
    neurons: NeuronsFile
    connectivity: ConnectivityFile
    background_inputs: BackgroundInputsFile
    scaling: ScalingConfig = Field(default_factory=ScalingConfig)
    reference: ReferenceConfig | None = None
    stimuli: StimuliFile = Field(default_factory=StimuliFile)
    synapses: SynapsesFile = Field(default_factory=SynapsesFile)
    # The rows of connectivity.yaml's connections_file, read from the CSV file.
    connection_table: ConnectionTable | None = None


class NetworkConfig(FrozenConfig):
    """
    The whole network, read from the YAML files in ``configs/network/``.

    background_mode:
        "poisson" (default): each population gets its background input from
        independent Poisson generators.
        "mean_current": the Poisson input of every population is replaced by a
        constant current of the same mean (Potjans & Diesmann 2014, Fig. 5).
        The rate, weight and delay in ``background_inputs`` are used to compute
        that mean (step ``replace_background_by_mean_current`` in
        ``network/compensation.py``). No Poisson generator is created.

    bound_mode:
        What to do with a drawn weight or delay that falls outside its
        allowed range (a weight of the wrong sign, a delay below its
        minimum). "redraw" (default): draw again until the value is
        allowed. "clip": replace the value by the limit, as the HuMAM
        model does. Applies to all weights and delays of the network.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    populations: dict[str, PopulationConfig]
    # All connections as one table (config/connection_table.py). The rows of
    # connectivity.yaml, as a list, are turned into one, and a table is written
    # back as those rows.
    connections: Annotated[
        ConnectionTable,
        BeforeValidator(to_connection_table),
        PlainSerializer(lambda table: table.to_yaml_rows(), return_type=list),
    ]

    background_inputs: dict[str, BackgroundInputConfig]
    background_mode: Literal["poisson", "mean_current"] = "poisson"
    bound_mode: Literal["redraw", "clip"] = "redraw"
    stimuli: list[StimulusConfig] = Field(default_factory=list)
    scaling: ScalingConfig

    reference: ReferenceConfig | None = None
    synapses: dict[str, SynapseEntry] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_stimulus_targets_exist(self) -> NetworkConfig:
        for stimulus in self.stimuli:
            unknown = [t for t in stimulus.targets if t not in self.populations]
            if unknown:
                raise ValueError(
                    f"Stimulus of type {stimulus.type!r} targets unknown "
                    f"population(s): {unknown}."
                )
        return self

    @model_validator(mode="after")
    def _check_one_connection_per_synapse(self) -> NetworkConfig:
        repeated = sorted(self.connections.duplicates(["source", "target", "synapse"]), key=str)
        if repeated:
            raise ValueError(
                f"connectivity.yaml has more than one entry for (source, target, synapse) "
                f"{repeated}. A pair takes one entry per synapse; to connect it twice "
                "(e.g. AMPA and NMDA), give each entry its own synapse."
            )
        return self

    @model_validator(mode="after")
    def _check_project_distributions_on_connections_only(self) -> NetworkConfig:
        users = [(f"background input of {name}", b) for name, b in self.background_inputs.items()]
        users += [(f"stimulus of {s.targets}", s) for s in self.stimuli if not isinstance(s, DcStimulusConfig)]
        for user, item in users:
            for what in ("weight", "delay"):
                distribution = getattr(item, what).distribution
                if distribution not in SHARED_DISTRIBUTIONS:
                    raise ValueError(
                        f"The {user} has a {what} from project distribution {distribution!r}; "
                        f"background inputs and stimuli take {', '.join(SHARED_DISTRIBUTIONS)} only."
                    )
        return self

    @model_validator(mode="after")
    def _check_one_to_one_sizes(self) -> NetworkConfig:
        table = self.connections
        for i in np.flatnonzero(table["rule"] == "one_to_one"):
            source, target = table["source"][i], table["target"][i]
            sizes = [self.populations[name].size if name in self.populations else None
                     for name in (source, target)]
            if None not in sizes and sizes[0] != sizes[1]:
                raise ValueError(
                    f"Connection {source} -> {target}: one_to_one needs populations of the same "
                    f"size; they have {sizes[0]} and {sizes[1]} neurons."
                )
        return self

    @model_validator(mode="after")
    def _check_shared_generators(self) -> NetworkConfig:
        groups: dict[str, list[str]] = {}
        for name, entry in self.background_inputs.items():
            if entry.generator is not None:
                groups.setdefault(entry.generator, []).append(name)
        if groups and self.background_mode == "mean_current":
            raise ValueError(
                f"background_inputs.yaml: generator {sorted(groups)[0]!r} is set, but "
                "background_mode is mean_current, which creates no generators."
            )
        # One generator fires at one rate (rate x indegree) through one synapse
        # model (the simulator connects a device through one model). Rate and
        # indegree are compared one by one, not their product: that holds
        # whether the network is prepared or not (a prepared rate is already
        # rate x indegree), and after any K_scaling.
        indegree = {name: pop.background_indegree for name, pop in self.populations.items()}
        for generator, names in groups.items():
            inputs = {
                name: (
                    self.background_inputs[name].rate,
                    indegree.get(name),
                    self.background_inputs[name].synapse,
                )
                for name in names
            }
            first = names[0]
            different = [name for name in names if inputs[name] != inputs[first]]
            if different:
                raise ValueError(
                    f"background_inputs.yaml: the populations of generator {generator!r} need "
                    "the same rate, background_indegree and synapse (rate, indegree, synapse): "
                    f"{first} has {inputs[first]}, {different[0]} has {inputs[different[0]]}."
                )
        return self

    @model_validator(mode="after")
    def _check_synapses(self) -> NetworkConfig:
        # Connections: checked once per synapse name, on whole columns.
        table = self.connections
        synapse = table["synapse"]
        for name in sorted({s for s in synapse.tolist() if s is not None}):
            uses = synapse == name
            first = int(np.flatnonzero(uses)[0])
            user = f"connection {table['source'][first]} -> {table['target'][first]}"
            if name not in self.synapses:
                raise ValueError(
                    f"The {user} uses synapse {name!r}, which is not defined in synapses.yaml."
                )
            psp = uses & (table["weight.unit"] == "PSP")
            if self.synapses[name].receptor_port is not None and psp.any():
                first = int(np.flatnonzero(psp)[0])
                user = f"connection {table['source'][first]} -> {table['target'][first]}"
                raise ValueError(
                    f"The {user} has a unit: PSP weight on receptor port "
                    f"{self.synapses[name].receptor_port} (synapse {name!r}). "
                    "PSP weights are converted with tau_syn_ex/tau_syn_in, which describe the "
                    "default port only; give this weight as unit: PSC or native."
                )

        users = [(f"background input of {name}", b) for name, b in self.background_inputs.items()]
        users += [
            (f"stimulus of {s.targets}", s)
            for s in self.stimuli
            if not isinstance(s, DcStimulusConfig)
        ]
        for user, item in users:
            if item.synapse is None:
                continue
            if item.synapse not in self.synapses:
                raise ValueError(
                    f"The {user} uses synapse {item.synapse!r}, which is not defined in "
                    "synapses.yaml."
                )
            # The PSP-to-PSC conversion uses tau_syn_ex/tau_syn_in, the time
            # constants of the default port; another port has its own.
            if self.synapses[item.synapse].receptor_port is not None and item.weight.unit == "PSP":
                raise ValueError(
                    f"The {user} has a unit: PSP weight on receptor port "
                    f"{self.synapses[item.synapse].receptor_port} (synapse {item.synapse!r}). "
                    "PSP weights are converted with tau_syn_ex/tau_syn_in, which describe the "
                    "default port only; give this weight as unit: PSC or native."
                )
        return self

    def receptor_port(self, synapse: str | None) -> int | None:
        """The receptor port of a synapse name (``None``: the default port)."""
        return None if synapse is None else self.synapses[synapse].receptor_port
