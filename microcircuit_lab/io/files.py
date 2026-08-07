"""
Utilities for reading and writing configuration files.

This module intentionally performs no interpretation of the configuration.
It only reads/writes YAML files as plain Python dictionaries.

Construction of validated configuration objects is handled elsewhere.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from dataclasses import dataclass

import yaml


def read_yaml(path: str | Path) -> dict[str, Any]:
    """
    Read a YAML file.

    Parameters
    ----------
    path
        Path to the YAML file.

    Returns
    -------
    dict
        Parsed YAML contents.
    """
    path = Path(path)

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if data is None:
        return {}

    if not isinstance(data, dict):
        raise TypeError(
            f"Expected top-level mapping in '{path}', " f"got {type(data).__name__}."
        )

    return data


def read_network_directory(path: str | Path) -> NetworkFiles:
    """
    Read all YAML files from a network configuration directory.

    Parameters
    ----------
    path
        Path to configs/network/.

    Returns
    -------
    NetworkFiles
        Data class containing the raw contents of all configuration files.
    """
    path = Path(path)
    manifest = read_yaml(path / "network.yaml")

    return NetworkFiles(
        populations=read_yaml(path / manifest["populations"]),
        neurons=read_yaml(path / manifest["neurons"]),
        connectivity=read_yaml(path / manifest["connectivity"]),
        inputs=read_yaml(path / manifest["inputs"]),
        scaling=read_yaml(path / manifest["scaling"]),
        reference=read_yaml(path / manifest["reference"]),
    )


class FlowRecord(dict):
    """Marker: dump this mapping in YAML flow style (one line) via write_yaml."""


yaml.SafeDumper.add_representer(
    FlowRecord,
    lambda dumper, data: dumper.represent_mapping(
        "tag:yaml.org,2002:map", data, flow_style=True
    ),
)


def flow_records(records: list | dict) -> list | dict:
    """
    Mark each item of a list, or each value of a dict, to be written in
    YAML flow style (nested mappings inside each record are marked too).

    Intended for large, uniform, generator-written tables -- e.g. thousands
    of connectivity rows -- where full YAML block style costs ~10x the
    lines for no readability gain. Leave hand-edited files (e.g. the toy
    network template) in normal block style instead. Apply to the specific
    field(s) that hold the table before calling write_yaml, e.g.:

        write_yaml(path, {"connections": flow_records(connections)})
    """

    def _wrap(value: Any) -> Any:
        if isinstance(value, dict):
            return FlowRecord({key: _wrap(item) for key, item in value.items()})
        return value

    if isinstance(records, list):
        return [_wrap(item) for item in records]
    if isinstance(records, dict):
        return {key: _wrap(item) for key, item in records.items()}
    raise TypeError(f"flow_records expects a list or dict, got {type(records).__name__}.")


def write_yaml(
    path: str | Path,
    data: dict[str, Any],
    *,
    header_comment: str | None = None,
) -> None:
    """
    Write a mapping as YAML.

    Use :func:`flow_records` on specific fields beforehand to keep large
    uniform tables compact; everything else is written in normal block
    style. ``header_comment`` is written as ``#``-prefixed lines above
    the YAML content -- e.g. to record generation-time provenance
    (was some non-default option used?) directly in a file that will
    otherwise be read on its own, long after the generating command's
    console output is gone.
    """

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    text = yaml.safe_dump(data, sort_keys=False, default_flow_style=False, width=100_000)
    if header_comment:
        prefixed = "\n".join(f"# {line}" if line else "#" for line in header_comment.splitlines())
        text = f"{prefixed}\n{text}"

    path.write_text(text, encoding="utf-8")


@dataclass(frozen=True)
class NetworkFiles:
    """
    Raw contents of the network configuration files.
    """

    populations: dict[str, Any]
    neurons: dict[str, Any]
    connectivity: dict[str, Any]
    inputs: dict[str, Any]
    scaling: dict[str, Any]
    reference: dict[str, Any]
