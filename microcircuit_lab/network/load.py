"""
Load a network from its folder, ``configs/network/<name>/``.

Two functions, for the two things you may want:

* :func:`read_network` -- the network exactly as written in its files, checked
  (every field against the models in :mod:`microcircuit_lab.config`, and the
  references between files: a population names an existing neuron, a
  connection names existing populations). Use it to inspect or change a
  network before it is prepared, e.g. to set another scaling.
* :func:`load_network` -- the same network prepared for the simulation (see
  :func:`microcircuit_lab.network.prepare.prepare_network`). This is what
  ``Simulation.from_yaml`` and ``microcircuit-lab run`` use, and what a builder
  can call to check what it wrote.

A problem raises a ``ValueError`` that names the folder, the file and the
field, e.g. ``populations.yaml: populations.0.size: Input should be greater
than 0``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from microcircuit_lab.config.network import NetworkConfig, NetworkDirectory, NetworkManifest

from microcircuit_lab.config.neurons import NeuronConfig

from microcircuit_lab.config.populations import PopulationConfig
from microcircuit_lab.network.prepare import prepare_network
from microcircuit_lab.yaml_files import read_yaml

# Shown under an error about an unknown stimulus type, weight or delay
# distribution, so whoever wants to add one knows where to look.
_HOW_TO_ADD = 'To add a new one, see "Changing the core" in CONTRIBUTING.md.'


def load_network(folder: str | Path) -> NetworkConfig:
    """
    Read a network folder and prepare it for the simulation.

    Parameters
    ----------
    folder
        The network folder, e.g. ``configs/network/pd14``.

    Returns
    -------
    NetworkConfig
        The network ready to simulate: weights in pA, scaling applied and
        compensation currents added.
    """

    return prepare_network(read_network(folder))


def read_network(folder: str | Path) -> NetworkConfig:
    """
    Read a network folder as written, without preparing it.

    Parameters
    ----------
    folder
        The network folder, e.g. ``configs/network/pd14``.

    Returns
    -------
    NetworkConfig
        The network as described by its files (weights still in the units
        they were written in, no scaling applied).
    """

    return assemble_network(read_network_files(folder))


def read_network_files(folder: str | Path) -> NetworkDirectory:
    """
    Read every file of a network folder and check each one on its own.

    ``network.yaml`` names the other files. References between files are not
    checked here (that is :func:`read_network`).
    """

    folder = Path(folder)
    manifest = NetworkManifest.model_validate(read_yaml(folder / "network.yaml"))

    parts: dict[str, Any] = {
        "manifest": manifest,
        "populations": read_yaml(folder / manifest.populations),
        "neurons": read_yaml(folder / manifest.neurons),
        "connectivity": read_yaml(folder / manifest.connectivity),
        "background_inputs": read_yaml(folder / manifest.background_inputs),
    }
    if manifest.scaling is not None:
        parts["scaling"] = read_yaml(folder / manifest.scaling)
    if manifest.reference is not None:
        parts["reference"] = read_yaml(folder / manifest.reference)
    if manifest.stimuli is not None:
        parts["stimuli"] = read_yaml(folder / manifest.stimuli)
    if manifest.synapses is not None:
        parts["synapses"] = read_yaml(folder / manifest.synapses)

    try:
        return NetworkDirectory.model_validate(parts)
    except ValidationError as error:
        raise ValueError(_describe_problems(folder, manifest, error)) from error


def _describe_problems(folder: Path, manifest: NetworkManifest, error: ValidationError) -> str:
    """One line per problem, as ``<file>: <field path>: <message>``.

    The first element of a pydantic error location is the part name
    (``populations``, ``neurons``, ...); the manifest says which file holds it.
    An unknown stimulus ``type`` or ``distribution`` also gets a pointer to
    where new ones are added.
    """

    lines = [f"Invalid network config in {folder}:"]
    point_to_contributing = False
    for problem in error.errors():
        part, *field = problem["loc"] or ("network.yaml",)
        file_name = "network.yaml" if part == "manifest" else getattr(manifest, str(part), part)
        field_path = ".".join(str(item) for item in field)
        lines.append(f"  {file_name}: {field_path or '(whole file)'}: {problem['msg']}")
        if problem["type"] == "union_tag_invalid" or (
            problem["type"] == "literal_error" and field and field[-1] == "distribution"
        ):
            point_to_contributing = True
    if point_to_contributing:
        lines.append(_HOW_TO_ADD)
    return "\n".join(lines)


def assemble_network(directory: NetworkDirectory) -> NetworkConfig:
    """Check the references between files and build the :class:`NetworkConfig`.

    :func:`read_network` is :func:`read_network_files` followed by this; call
    them separately to change the files' content in memory in between.

    A population's neuron is looked up by name and stored in the population;
    connections, background inputs and stimuli must name existing populations (and
    synapses, checked by :class:`NetworkConfig`).
    """

    neurons = {
        name: NeuronConfig(
            name=name,
            model=entry.model,
            parameters=entry.parameters,
            psp_conversion_aliases=entry.psp_conversion_aliases,
        )
        for name, entry in directory.neurons.neurons.items()
    }

    populations: dict[str, PopulationConfig] = {}
    for entry in directory.populations.populations:
        if entry.neuron not in neurons:
            raise ValueError(
                f"Population '{entry.name}' references neuron '{entry.neuron}', "
                "which is not defined in neurons.yaml."
            )
        if entry.name in populations:
            raise ValueError(f"Duplicate population name '{entry.name}'.")
        populations[entry.name] = PopulationConfig(
            name=entry.name,
            size=entry.size,
            neuron=neurons[entry.neuron],
            initial_state=entry.initial_state,
            background_indegree=entry.background_indegree,
        )

    for connection in directory.connectivity.connections:
        for role, name in (("source", connection.source), ("target", connection.target)):
            if name not in populations:
                raise ValueError(
                    f"Connection {role} population '{name}' is not defined in populations.yaml."
                )

    for name in directory.background_inputs.background_inputs:
        if name not in populations:
            raise ValueError(
                f"background_inputs.yaml references population '{name}', "
                "which is not defined in populations.yaml."
            )

    return NetworkConfig(
        populations=populations,
        connections=list(directory.connectivity.connections),
        background_inputs=dict(directory.background_inputs.background_inputs),
        background_mode=directory.background_inputs.background_mode,
        bound_mode=directory.connectivity.bound_mode,
        stimuli=directory.stimuli.stimuli,
        scaling=directory.scaling,
        reference=directory.reference,
        synapses=dict(directory.synapses.synapses),
    )
