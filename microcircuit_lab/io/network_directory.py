"""
Write a whole ``configs/network/<name>/`` directory from in-memory payloads.

The write-side counterpart to
:func:`~microcircuit_lab.io.files.read_network_directory`: a generator
builds the parts as plain lists and dicts (from published tables, pickles,
recordings -- whatever its source data is) and
:func:`write_network_directory` turns them into the on-disk schema --
manifest, one file per part, the large uniform tables in the compact
one-record-per-line style -- then runs
:func:`~microcircuit_lab.io.network_validation.validate_network_config` on
the result. A generator's whole "output" half becomes one call.

It invents no model values: a field a payload omits is either a schema
default or a validation error. The only things filled in are the manifest
filenames (conventional unless ``manifest=`` overrides them) and the empty
``scaling`` / ``reference`` files.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.io.files import flow_records, write_yaml
from microcircuit_lab.io.network_validation import validate_network_config

#: Part -> file name, when ``manifest`` is not given. ``read_network_directory``
#: reads exactly these names; a generator overrides one only to rename or
#: split a file.
CONVENTIONAL_FILE_NAMES: dict[str, str] = {
    "populations": "populations.yaml",
    "neurons": "neurons.yaml",
    "connectivity": "connectivity.yaml",
    "background_inputs": "background_inputs.yaml",
    "scaling": "scaling.yaml",
    "reference": "reference.yaml",
    "stimuli": "stimuli.yaml",
}

def _to_plain(value: Any) -> Any:
    """Recursively turn pydantic models into plain dicts so ``yaml`` can
    dump them -- a caller that already has typed configs is not punished
    for passing them, and a stray model becomes a clear place to look
    rather than a ``yaml`` representer error."""
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, Mapping):
        return {key: _to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(item) for item in value]
    return value


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
    manifest: Mapping[str, str] | None = None,
    provenance: str | None = None,
) -> NetworkConfig:
    """Write ``path`` as a network-config directory and validate it.

    ``populations`` and ``connections`` are the row lists; ``neurons`` and
    ``background_inputs`` are the name-keyed maps -- in every case the
    single wrapper key each file has (``populations:``, ``connections:``,
    ...) is added here, not by the caller. ``reference`` is likewise the
    inner ``{population: rate}`` map, not ``{"full_mean_rates": ...}``.
    ``scaling`` is passed as its field mapping (it has several); ``None``
    writes an all-defaults file.

    ``stimuli=None`` omits ``stimuli.yaml`` and its manifest key; pass a
    list to write it. ``background_mode`` is written into
    ``background_inputs.yaml`` only when it is ``"dc"`` (``"poisson"`` is
    the schema default). ``provenance``, if given, is written as a ``#``
    header on every file -- e.g. the command and options that produced it.
    ``manifest`` overrides the conventional file names and is then used
    exactly as given.

    Always overwrites, always validates: returns the resolved, preprocessed
    :class:`~microcircuit_lab.config.network.NetworkConfig` from
    :func:`~microcircuit_lab.io.network_validation.validate_network_config`,
    or raises from there with the offending file and field named.
    """

    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)

    include_stimuli = stimuli is not None

    file_names = dict(manifest) if manifest is not None else {
        part: name
        for part, name in CONVENTIONAL_FILE_NAMES.items()
        if part != "stimuli" or include_stimuli
    }

    background_payload: dict[str, Any] = {}
    if background_mode != "poisson":
        background_payload["background_mode"] = background_mode
    background_payload["background_inputs"] = flow_records(_to_plain(dict(background_inputs)))

    # populations / connections / background_inputs go one-record-per-line:
    # they run to thousands of uniform rows for multi-area networks and the
    # compact form parses identically (see the package README). neurons /
    # scaling / reference stay in readable block style.
    payloads: dict[str, Any] = {
        "network.yaml": file_names,
        "populations.yaml": {"populations": flow_records(_to_plain(list(populations)))},
        "neurons.yaml": {"neurons": _to_plain(dict(neurons))},
        "connectivity.yaml": {"connections": flow_records(_to_plain(list(connections)))},
        "background_inputs.yaml": background_payload,
        "scaling.yaml": _to_plain(dict(scaling)) if scaling is not None else {},
        "reference.yaml": {
            "full_mean_rates": _to_plain(dict(reference)) if reference is not None else {}
        },
    }
    if include_stimuli:
        payloads["stimuli.yaml"] = {"stimuli": _to_plain(list(stimuli))}

    for name, payload in payloads.items():
        write_yaml(directory / name, payload, header_comment=provenance)

    return validate_network_config(directory)
