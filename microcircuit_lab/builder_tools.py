"""
Everything a builder needs, in one import.

A builder turns a model's data (published tables, pickles, recordings) into a
network folder ``configs/network/<name>/``::

    from microcircuit_lab.builder_tools import delay, weight, write_network_directory

    write_network_directory(
        "configs/network/my_model",
        populations=[{"name": "E", "size": 800, "neuron": "lif", ...}],
        neurons={"lif": {"model": "iaf_psc_exp", "parameters": {...}}},
        connections=[{"source": "E", "target": "E", "n_synapses": 8000,
                      "weight": weight(0.15, unit="PSP", rel_std=0.1),
                      "delay": delay(1.5, rel_std=0.5)}],
        background_inputs={"E": {"rate": 8.0, "weight": weight(0.15, unit="PSP"),
                                 "delay": delay(1.5)}},
    )

* :func:`write_network_directory` writes every file of the folder and checks
  the result (with :func:`microcircuit_lab.network.load.load_network`), so a
  mistake raises with the file and the field named.
* :func:`weight` and :func:`delay` build the ``weight`` / ``delay`` entries
  every connection, background input and stimulus needs.
* :func:`num_synapses_from_conn_prob` turns a connection probability into a
  number of synapses (Potjans & Diesmann 2014).
* :func:`psp_to_psc_iaf_psc_exp` converts a PSP amplitude (mV) into a current
  (pA), for a builder that wants to write ``unit: PSC``.

None of these invents model values: a field a builder leaves out is either a
default of the config models or an error. Using them is optional; files
written any other way are checked the same way when the network is loaded.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Literal

import numpy as np

from microcircuit_lab.config.connection_table import ConnectionTable
from microcircuit_lab.config.connectivity import DelayDistribution, WeightDistribution
from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.network.load import load_network
from microcircuit_lab.network.psp_psc_conversion import psp_to_psc_iaf_psc_exp
from microcircuit_lab.yaml_files import flow_records, write_yaml

__all__ = [
    "delay",
    "num_synapses_from_conn_prob",
    "psp_to_psc_iaf_psc_exp",
    "weight",
    "write_network_directory",
]


def _distribution(rel_std: float, explicit: str | None) -> str:
    """The distribution to write: ``explicit`` if given, else ``fixed`` for
    no spread (``rel_std == 0``) and ``normal`` otherwise."""
    if explicit is not None:
        return explicit
    return "fixed" if rel_std == 0.0 else "normal"


def weight(
    mean: float,
    *,
    unit: str,
    rel_std: float = 0.0,
    distribution: str | None = None,
) -> dict[str, Any]:
    """
    A ``weight`` entry for a connection, background input or stimulus.

    Parameters
    ----------
    mean
        The amplitude, read according to ``unit``.
    unit
        ``"PSP"`` (mV, converted to pA with the target neuron's parameters),
        ``"PSC"`` (pA, used as given) or ``"native"`` (used as given, without
        any interpretation).
    rel_std
        Standard deviation divided by ``|mean|``; 0 for a fixed weight.
    distribution
        ``"fixed"``, ``"normal"``, ``"uniform"`` or ``"lognormal"``. By default ``fixed`` when
        ``rel_std`` is 0 and ``normal`` otherwise.

    Returns
    -------
    dict
        The entry as written in the YAML file. It is checked against
        :class:`~microcircuit_lab.config.connectivity.WeightDistribution`, so a bad value
        raises here.
    """
    return WeightDistribution(
        mean=mean,
        rel_std=rel_std,
        unit=unit,
        distribution=_distribution(rel_std, distribution),
    ).model_dump()


def delay(
    mean: float,
    *,
    rel_std: float = 0.0,
    distribution: str | None = None,
    minimum: float | None = None,
) -> dict[str, Any]:
    """
    A ``delay`` entry for a connection, background input or stimulus.

    Parameters
    ----------
    mean
        Mean delay in ms.
    rel_std
        Standard deviation divided by ``mean``; 0 for a fixed delay.
    distribution
        As in :func:`weight`.
    minimum
        Smallest allowed delay in ms; left out of the file when not given (the
        default is then half the simulation step).

    Returns
    -------
    dict
        The entry as written in the YAML file, checked against
        :class:`~microcircuit_lab.config.connectivity.DelayDistribution`.
    """
    return DelayDistribution(
        mean=mean,
        rel_std=rel_std,
        distribution=_distribution(rel_std, distribution),
        minimum=minimum,
    ).model_dump(exclude_none=True)


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
        The fields of ``scaling.yaml``; ``None`` writes no ``scaling.yaml`` (the
        network runs at full scale).
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
        The network ready to simulate, from
        :func:`~microcircuit_lab.network.load.load_network`. A mistake raises
        there, with the file and the field named.
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

    return load_network(directory)


def num_synapses_from_conn_prob(
    conn_prob: float,
    n_source: int,
    n_target: int,
) -> int:
    """
    Compute the total number of synapses from a connection probability.

    Parameters
    ----------
    conn_prob
        Connection probability.

    n_source
        Number of source neurons.

    n_target
        Number of target neurons.

    Returns
    -------
    int
        Expected total number of synapses.
    """

    if conn_prob <= 0.0:
        return 0

    prod = n_source * n_target

    num_syn = np.log(1.0 - conn_prob) / np.log((prod - 1.0) / prod)

    return int(round(num_syn))
