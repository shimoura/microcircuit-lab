"""
Write a whole ``configs/network/<name>/`` directory from in-memory payloads.

The write-side counterpart to
:func:`~microcircuit_lab.io.files.read_network_directory`: a generator
builds the parts as plain lists and dicts (from published tables, pickles,
recordings -- whatever its source data is) and
:func:`write_network_directory` turns them into the on-disk schema --
``network.yaml``, one file per part, the large uniform tables in the compact
one-record-per-line style -- then runs
:func:`~microcircuit_lab.io.network_validation.validate_network_config` on
the result. A generator's whole "output" half becomes one call.

It invents no model values: a field a payload omits is either a schema
default or a validation error. The only things filled in are the file names
and the empty ``scaling`` / ``reference`` files.

:func:`weight` and :func:`delay` build the ``weight`` / ``delay`` dicts that
every connection and background input needs.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Literal

from microcircuit_lab.config.network import (
    DelayDistribution,
    NetworkConfig,
    WeightDistribution,
)
from microcircuit_lab.io.files import flow_records, write_yaml
from microcircuit_lab.io.network_validation import validate_network_config


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
    """A connection or background weight.

    ``unit`` selects how ``mean`` is read -- ``"PSP"`` (mV, converted for
    the target neuron), ``"PSC"`` (pA, as given) or ``"native"`` (as given,
    no interpretation). The values are checked by
    :class:`~microcircuit_lab.config.network.WeightDistribution`, so a bad
    one raises here. ``distribution`` defaults to ``fixed`` when ``rel_std``
    is 0 and ``normal`` otherwise; pass it for anything else
    (e.g. ``"lognormal"``).
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
) -> dict[str, Any]:
    """A connection or background delay, ``mean`` in ms. ``distribution``
    is chosen as in :func:`weight`."""
    return DelayDistribution(
        mean=mean,
        rel_std=rel_std,
        distribution=_distribution(rel_std, distribution),
    ).model_dump()


def write_network_directory(
    path: str | Path,
    *,
    populations: Iterable[Mapping[str, Any]],
    neurons: Mapping[str, Mapping[str, Any]],
    connections: Iterable[Mapping[str, Any]],
    background_inputs: Mapping[str, Mapping[str, Any]],
    background_mode: Literal["poisson", "dc"] = "poisson",
    scaling: Mapping[str, Any] | None = None,
    reference: Mapping[str, float] | None = None,
    stimuli: Iterable[Mapping[str, Any]] | None = None,
) -> NetworkConfig:
    """Write ``path`` as a network-config directory and validate it.

    ``populations`` and ``connections`` are the row lists; ``neurons`` and
    ``background_inputs`` are the name-keyed maps -- in every case the
    single wrapper key each file has (``populations:``, ``connections:``,
    ...) is added here, not by the caller. ``reference`` is likewise the
    inner ``{population: rate}`` map, not ``{"full_mean_rates": ...}``.
    ``scaling`` is passed as its field mapping (it has several); ``None``
    writes an all-defaults file.

    ``stimuli=None`` omits ``stimuli.yaml``; pass a list to write it.
    ``background_mode`` is written into ``background_inputs.yaml`` only when
    it is ``"dc"`` (``"poisson"`` is the schema default).

    Always overwrites, always validates: returns the resolved, preprocessed
    :class:`~microcircuit_lab.config.network.NetworkConfig` from
    :func:`~microcircuit_lab.io.network_validation.validate_network_config`,
    or raises from there with the offending file and field named.
    """

    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)

    file_names = {
        "populations": "populations.yaml",
        "neurons": "neurons.yaml",
        "connectivity": "connectivity.yaml",
        "background_inputs": "background_inputs.yaml",
        "scaling": "scaling.yaml",
        "reference": "reference.yaml",
    }
    if stimuli is not None:
        file_names["stimuli"] = "stimuli.yaml"

    background_payload: dict[str, Any] = {}
    if background_mode != "poisson":
        background_payload["background_mode"] = background_mode
    background_payload["background_inputs"] = flow_records(dict(background_inputs))

    # populations / connections / background_inputs go one-record-per-line:
    # they run to thousands of uniform rows for multi-area networks and the
    # compact form parses identically (see the package README). neurons /
    # scaling / reference stay in readable block style.
    payloads: dict[str, Any] = {
        "network.yaml": file_names,
        "populations.yaml": {"populations": flow_records(list(populations))},
        "neurons.yaml": {"neurons": dict(neurons)},
        "connectivity.yaml": {"connections": flow_records(list(connections))},
        "background_inputs.yaml": background_payload,
        "scaling.yaml": dict(scaling) if scaling is not None else {},
        "reference.yaml": {
            "full_mean_rates": dict(reference) if reference is not None else {}
        },
    }
    if stimuli is not None:
        payloads["stimuli.yaml"] = {"stimuli": list(stimuli)}

    for name, payload in payloads.items():
        write_yaml(directory / name, payload)

    return validate_network_config(directory)
