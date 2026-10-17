"""
Utilities for reading and writing configuration files.

:func:`read_yaml` / :func:`write_yaml` do no interpretation -- they move
plain dictionaries to and from disk. :func:`read_network_directory` is the
one exception: it reads a whole ``configs/network/<name>/`` directory and
validates it against the schema in :mod:`microcircuit_lab.config.schema`,
so a malformed file fails here with a clear message rather than deeper in
the pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from microcircuit_lab.config.schema import NetworkDirectory, NetworkManifest


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


def read_network_directory(path: str | Path) -> NetworkDirectory:
    """
    Read and validate a ``configs/network/<name>/`` directory.

    ``network.yaml`` names the other files; each is read and checked
    against its model in :mod:`microcircuit_lab.config.schema`. An unknown,
    missing or invalid field raises a ``ValueError`` that names the
    directory, the file and the field (e.g. ``populations.yaml:
    populations.0.size: Input should be greater than 0``). Cross-file
    references (a population's neuron, a connection's populations) are
    resolved later, when :class:`~microcircuit_lab.io.config.NetworkConfigLoader`
    assembles the network.
    """
    path = Path(path)
    manifest = NetworkManifest.model_validate(read_yaml(path / "network.yaml"))

    parts: dict[str, Any] = {
        "manifest": manifest,
        "populations": read_yaml(path / manifest.populations),
        "neurons": read_yaml(path / manifest.neurons),
        "connectivity": read_yaml(path / manifest.connectivity),
        "background_inputs": read_yaml(path / manifest.background_inputs),
        "scaling": read_yaml(path / manifest.scaling),
        "reference": read_yaml(path / manifest.reference),
    }
    if manifest.stimuli is not None:
        parts["stimuli"] = read_yaml(path / manifest.stimuli)

    try:
        return NetworkDirectory.model_validate(parts)
    except ValidationError as error:
        raise ValueError(_describe_problems(path, manifest, error)) from error


def _describe_problems(path: Path, manifest: NetworkManifest, error: ValidationError) -> str:
    """One line per problem, as ``<file>: <field path>: <message>``.

    The first element of a pydantic error location is the part name
    (``populations``, ``neurons``, ...); the manifest says which file holds it.
    """
    lines = [f"Invalid network config in {path}:"]
    for problem in error.errors():
        part, *field = problem["loc"] or ("network.yaml",)
        file_name = "network.yaml" if part == "manifest" else getattr(manifest, str(part), part)
        field_path = ".".join(str(item) for item in field)
        lines.append(f"  {file_name}: {field_path or '(whole file)'}: {problem['msg']}")
    return "\n".join(lines)


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
