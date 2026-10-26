"""
Load a network from its folder, ``configs/network/<name>/``.

Two functions, for the two things you may want:

* :func:`read_network`: the network exactly as written in its files, checked
  (every field against the models in :mod:`microcircuit_lab.config`, and the
  references between files: a population names an existing neuron, a
  connection names existing populations). Use it to inspect or change a
  network before it is prepared, e.g. to scale it.
* :func:`load_network`: the same network prepared for the simulation (see
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

from microcircuit_lab.config.connection_table import ConnectionTable
from microcircuit_lab.config.network import (
    NetworkConfig,
    NetworkDirectory,
    NetworkManifest,
)
from microcircuit_lab.config.neurons import NeuronConfig
from microcircuit_lab.config.populations import PopulationConfig
from microcircuit_lab.network.prepare import prepare_network
from microcircuit_lab.yaml_files import read_yaml

# Shown under an error about an unknown stimulus type, so whoever wants to add
# one knows where to look. (An unknown distribution or rule is a project one,
# which the backend looks up: see its check().)
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
        The network ready to simulate: each background rate per synapse
        turned into the rate of its generator, or into a constant current
        with ``background_mode: mean_current`` (see
        :func:`~microcircuit_lab.network.prepare.prepare_network`).
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
        The network as described by its files, e.g. to change it, or to
        scale it with :func:`~microcircuit_lab.network.scaling.scale_network`.
    """

    return assemble_network(read_network_files(folder))


def read_network_files(folder: str | Path) -> NetworkDirectory:
    """
    Read every file of a network folder and check each one on its own.

    ``network.yaml`` names the other files. References between files are not
    checked here (that is :func:`read_network`).
    """

    folder = Path(folder)
    if not (folder / "network.yaml").is_file():
        raise FileNotFoundError(_missing_network_message(folder))
    manifest = NetworkManifest.model_validate(read_yaml(folder / "network.yaml"))

    connectivity = read_yaml(folder / manifest.connectivity)

    parts: dict[str, Any] = {
        "manifest": manifest,
        "populations": read_yaml(folder / manifest.populations),
        "neurons": read_yaml(folder / manifest.neurons),
        "connectivity": connectivity,
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
    # A large network keeps its connections in a CSV file.
    if isinstance(connectivity.get("connections_file"), str):
        csv_path = folder / connectivity["connections_file"]
        if not csv_path.is_file():
            raise FileNotFoundError(
                f"{folder}: {manifest.connectivity} names connections_file "
                f"'{connectivity['connections_file']}', but there is no file {csv_path}."
            )
        parts["connection_table"] = ConnectionTable.read_csv(csv_path)

    try:
        return NetworkDirectory.model_validate(parts)
    except ValidationError as error:
        raise ValueError(_describe_problems(folder, manifest, error)) from error


def _missing_network_message(folder: Path) -> str:
    """One line: the missing folder, and the networks found next to it."""
    message = f"No network at {folder} (no network.yaml)."
    parent = folder.parent
    found = (
        sorted(p.name for p in parent.iterdir() if (p / "network.yaml").is_file())
        if parent.is_dir()
        else []
    )
    if found:
        message += f" Networks in {parent}: {', '.join(found)}"
    return message


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
        if problem["type"] == "union_tag_invalid":
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

    connections = directory.connection_table
    if connections is None:
        connections = ConnectionTable.from_yaml_rows(directory.connectivity.connections)
    for role in ("source", "target"):
        unknown = sorted(set(connections[role].tolist()) - set(populations))
        if unknown:
            raise ValueError(
                f"Connection {role} population '{unknown[0]}' is not defined in populations.yaml."
            )

    for name in directory.background_inputs.background_inputs:
        if name not in populations:
            raise ValueError(
                f"background_inputs.yaml references population '{name}', "
                "which is not defined in populations.yaml."
            )

    return NetworkConfig(
        populations=populations,
        connections=connections,
        background_inputs=dict(directory.background_inputs.background_inputs),
        background_mode=directory.background_inputs.background_mode,
        bound_mode=directory.connectivity.bound_mode,
        stimuli=directory.stimuli.stimuli,
        scaling=directory.scaling,
        reference=directory.reference,
        synapses=dict(directory.synapses.synapses),
    )
