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
                      "weight": weight(87.8, unit="pA", rel_std=0.1),
                      "delay": delay(1.5, rel_std=0.5)}],
        background_inputs={"E": {"rate": 8.0, "weight": weight(87.8, unit="pA"),
                                 "delay": delay(1.5)}},
    )

* :func:`write_network_directory` writes every file of the folder and checks
  the result (with :func:`microcircuit_lab.network.load.read_network`), so a
  mistake raises with the file and the field named.
* :func:`scale_network` returns a network scaled down (fewer neurons and
  synapses, stronger weights, the lost mean input as a current), and
  :func:`write_network` writes such a network as a folder.
* :func:`weight` and :func:`delay` build the ``weight`` / ``delay`` entries
  every connection, background input and stimulus needs.
* :func:`num_synapses_from_conn_prob` turns a connection probability into a
  number of synapses (Potjans & Diesmann 2014).
* :func:`psp_to_psc_iaf_psc_exp` converts a PSP amplitude (mV) into the
  current (pA) that produces it, for a model whose weights are given as PSPs
  (:func:`psc_to_psp` goes back). The core never converts a weight itself.

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
from microcircuit_lab.network.load import read_network
from microcircuit_lab.network.scaling import scale_network
from microcircuit_lab.yaml_files import flow_records, write_yaml

__all__ = [
    "delay",
    "num_synapses_from_conn_prob",
    "psc_to_psp",
    "psp_to_psc_iaf_psc_exp",
    "scale_network",
    "weight",
    "write_network",
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
    parameters: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    A ``weight`` entry for a connection, background input or stimulus.

    Parameters
    ----------
    mean
        The weight the simulator gets, in ``unit``.
    unit
        ``"pA"`` (a current), ``"nS"`` (a conductance) or ``"mV"`` (a jump of
        the membrane potential). Nothing is converted.
    rel_std
        Standard deviation divided by ``|mean|``; 0 for a fixed weight.
    distribution
        ``"fixed"``, ``"normal"``, ``"uniform"`` or ``"lognormal"``, or a project
        distribution (connections only). By default ``fixed`` when ``rel_std`` is 0
        and ``normal`` otherwise.
    parameters
        A project distribution's parameters.

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
        parameters=parameters,
    ).model_dump(exclude_none=True)


def delay(
    mean: float,
    *,
    rel_std: float = 0.0,
    distribution: str | None = None,
    minimum: float | None = None,
    parameters: Mapping[str, Any] | None = None,
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
    parameters
        A project distribution's parameters.

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
        parameters=parameters,
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


def psc_over_psp(
    C_m: float,
    tau_m: float,
    tau_syn: float,
) -> float:
    """
    Compute the conversion factor PSC / PSP.

    Parameters
    ----------
    C_m
        Membrane capacitance (pF).

    tau_m
        Membrane time constant (ms).

    tau_syn
        Synaptic time constant (ms).

    Returns
    -------
    float
        Factor converting PSP (mV) to PSC (pA).

    Notes
    -----
    This is the standard PSP-to-PSC conversion for a leaky
    integrate-and-fire neuron with a current-based synapse whose
    postsynaptic current decays as a single exponential (Rotter and
    Diesmann 1999). It only depends on the subthreshold membrane
    equation and the synaptic current kernel, so it holds for any
    neuron model with that dynamics, not one specific implementation.
    Potjans and Diesmann (2014) use it for their iaf_psc_exp
    populations, which is where it's most commonly seen in this field.
    """

    if np.isclose(tau_syn, tau_m):
        raise ValueError("tau_syn and tau_m must be different.")

    eps = tau_syn / tau_m

    return C_m * eps ** (-1.0 / (1.0 - eps)) / tau_m


def psp_to_psc_iaf_psc_exp(
    psp: float,
    C_m: float,
    tau_m: float,
    tau_syn: float,
) -> float:
    """
    Convert a PSP amplitude (mV) to the current amplitude (pA) that produces it.

    Holds for a current-based LIF neuron with exponential synaptic currents.
    It is named after NEST's ``iaf_psc_exp``, where people know it from, but it
    only depends on ``C_m``, ``tau_m`` and ``tau_syn`` (see
    :func:`psc_over_psp`), whatever the model is called.

    Parameters
    ----------
    psp
        The PSP amplitude, in mV.
    C_m
        Membrane capacitance, in pF.
    tau_m
        Membrane time constant, in ms.
    tau_syn
        Synaptic time constant, in ms.

    Returns
    -------
    float
        The current amplitude, in pA.
    """

    return psp * psc_over_psp(
        C_m=C_m,
        tau_m=tau_m,
        tau_syn=tau_syn,
    )


def psc_to_psp(
    psc: float,
    C_m: float,
    tau_m: float,
    tau_syn: float,
) -> float:
    """
    Convert a current amplitude (pA) to the PSP amplitude (mV) it produces; the
    inverse of :func:`psp_to_psc_iaf_psc_exp`.

    Parameters
    ----------
    psc
        The current amplitude, in pA.
    C_m, tau_m, tau_syn
        As in :func:`psp_to_psc_iaf_psc_exp`.

    Returns
    -------
    float
        The PSP amplitude, in mV.
    """

    return psc / psc_over_psp(
        C_m=C_m,
        tau_m=tau_m,
        tau_syn=tau_syn,
    )
