"""
Write a network folder from the content of its files, or from a network read
(or scaled) in memory.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Literal

from microcircuit_lab.config.connection_table import ConnectionTable
from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.network.load import read_network
from microcircuit_lab.yaml_files import flow_records, write_yaml


def write_network_directory(
    path: str | Path,
    *,
    populations: Iterable[Mapping[str, Any]],
    neurons: Mapping[str, Mapping[str, Any]],
    connections: Iterable[Mapping[str, Any]] | ConnectionTable,
    background_inputs: Mapping[str, Mapping[str, Any]],
    background_mode: Literal["poisson", "mean_current"] = "poisson",
    bound_mode: Literal["redraw", "clip"] = "redraw",
    scaling: Mapping[str, Any] | None = None,
    reference: Mapping[str, float] | None = None,
    stimuli: Iterable[Mapping[str, Any]] | None = None,
    synapses: Mapping[str, Mapping[str, Any]] | None = None,
    compact: bool = True,
) -> NetworkConfig:
    """
    Write a whole network folder and check it.

    Each argument is the content of one file, without the file's top-level key
    (``populations:``, ``connections:``, ...), which is added here.

    Parameters
    ----------
    path
        The network folder to write, e.g. ``configs/network/my_model``. Existing
        files are overwritten.
    populations
        One dict per population (``name``, ``size``, ``neuron``,
        ``initial_state``, ``background_indegree``).
    neurons
        ``{neuron name: {"model": ..., "parameters": {...}}}``.
    connections
        One dict per projection (``source``, ``target``, ``n_synapses`` or
        another ``rule`` with its number, ``weight``, ``delay``, optionally
        ``synapse``). Or, for a large network, a
        :class:`~microcircuit_lab.config.connection_table.ConnectionTable`,
        written as ``connections.csv``.
    background_inputs
        ``{population name: {"rate": ..., "weight": ..., "delay": ...}}``.
    background_mode
        ``"poisson"`` or ``"mean_current"``; written only when ``"mean_current"``.
    bound_mode
        ``"redraw"`` or ``"clip"``; written only when ``"clip"``.
    scaling
        The record of a scaled network (``scaling.yaml``), which
        :func:`write_network` passes on; ``None`` writes none.
    reference
        ``{population name: full-scale mean rate}``; ``None`` writes no
        ``reference.yaml``.
    stimuli
        The list of stimuli; ``None`` writes no ``stimuli.yaml``.
    synapses
        ``{synapse name: {"model": ..., "parameters": {...}, "receptor_port": ...}}``;
        ``None`` writes no ``synapses.yaml``.
    compact
        Connections are always written one per line. ``True`` writes populations
        and background inputs the same way; ``False`` writes them in block
        style, easier to read for a small network.

    Returns
    -------
    NetworkConfig
        The network as written, from
        :func:`~microcircuit_lab.network.load.read_network` (e.g. to scale it).
        A mistake raises there, with the file and the field named.
    """

    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)

    file_names = {
        "populations": "populations.yaml",
        "neurons": "neurons.yaml",
        "connectivity": "connectivity.yaml",
        "background_inputs": "background_inputs.yaml",
    }
    # The optional files, written only when given.
    optional = {
        "scaling": None if scaling is None else dict(scaling),
        "reference": None if reference is None else {"full_mean_rates": dict(reference)},
        "stimuli": None if stimuli is None else {"stimuli": list(stimuli)},
        "synapses": None if synapses is None else {"synapses": dict(synapses)},
    }
    for part, payload in optional.items():
        if payload is not None:
            file_names[part] = f"{part}.yaml"

    table = flow_records if compact else (lambda records: records)

    connectivity_payload: dict[str, Any] = {}
    if bound_mode != "redraw":
        connectivity_payload["bound_mode"] = bound_mode
    if isinstance(connections, ConnectionTable):
        # A large network: the table goes to a CSV file, named in connectivity.yaml.
        connections.write_csv(directory / "connections.csv")
        connectivity_payload["connections_file"] = "connections.csv"
    else:
        connectivity_payload["connections"] = flow_records(list(connections))

    background_payload: dict[str, Any] = {}
    if background_mode != "poisson":
        background_payload["background_mode"] = background_mode
    background_payload["background_inputs"] = table(dict(background_inputs))

    # connections (and, with compact, populations / background_inputs) go
    # one-record-per-line: they run to thousands of uniform rows for
    # multi-area networks and the compact form parses identically (see the
    # package README). neurons / scaling / reference stay in block style.
    payloads: dict[str, Any] = {
        "network.yaml": file_names,
        "populations.yaml": {"populations": table(list(populations))},
        "neurons.yaml": {"neurons": dict(neurons)},
        "connectivity.yaml": connectivity_payload,
        "background_inputs.yaml": background_payload,
    }
    for part, payload in optional.items():
        if payload is not None:
            payloads[f"{part}.yaml"] = payload

    for name, payload in payloads.items():
        write_yaml(directory / name, payload)

    return read_network(directory)


def write_network(
    network: NetworkConfig, path: str | Path, *, csv: bool = False, compact: bool = True
) -> NetworkConfig:
    """
    Write ``network`` as a network folder, e.g. one returned by
    :func:`scale_network`.

    Populations that share a neuron entry keep sharing it while their neurons
    are the same; a population whose neuron differs (e.g. its own compensation
    current in ``I_e``) gets an entry of its own, named after the population.

    Parameters
    ----------
    network
        The network as written (not prepared: background rates per synapse).
    path
        The folder to write, e.g. ``configs/network/pd14_downscaled``.
    csv
        Write the connections as ``connections.csv`` (for a large network)
        instead of in ``connectivity.yaml``.
    compact
        As for :func:`write_network_directory`.

    Returns
    -------
    NetworkConfig
        The network read back from the folder.
    """

    entries = {
        name: {"model": population.neuron.model, "parameters": population.neuron.parameters.model_dump(mode="json")}
        for name, population in network.populations.items()
    }
    # A neuron name is kept if all its populations have the same neuron.
    shared: dict[str, list] = {}
    for name, population in network.populations.items():
        shared.setdefault(population.neuron.name, []).append(entries[name])
    neurons: dict[str, dict[str, Any]] = {}
    populations = []
    for name, population in network.populations.items():
        same = all(entry == entries[name] for entry in shared[population.neuron.name])
        key = population.neuron.name if same else name
        neurons[key] = entries[name]
        row = population.model_dump(mode="json")
        row["neuron"] = key
        populations.append(row)

    def dump(item) -> dict[str, Any]:
        return item.model_dump(mode="json", exclude_none=True)

    return write_network_directory(
        path,
        populations=populations,
        neurons=neurons,
        connections=network.connections if csv else network.connections.to_yaml_rows(),
        background_inputs={name: dump(item) for name, item in network.background_inputs.items()},
        background_mode=network.background_mode,
        bound_mode=network.bound_mode,
        scaling=None if network.scaling is None else dump(network.scaling),
        reference=None if network.reference is None else network.reference.full_mean_rates,
        stimuli=[dump(item) for item in network.stimuli] or None,
        synapses={name: dump(item) for name, item in network.synapses.items()} or None,
        compact=compact,
    )
