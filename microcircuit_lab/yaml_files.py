"""
Read and write YAML files.

These functions do no interpretation: they move plain dictionaries to and from
disk. Checking what a file contains is the job of the models in
:mod:`microcircuit_lab.config` (see :mod:`microcircuit_lab.network.load` for a
network folder).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

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


class FlowRecord(dict):
    """Marker: dump this mapping in YAML flow style (one line) via write_yaml."""


class _Dumper(yaml.SafeDumper):
    """The YAML writer of :func:`write_yaml`: one-line ``FlowRecord`` mappings,
    and a value used twice written out twice, never as an anchor (``&id001``)
    and its alias, which people reading the file would not expect."""

    def ignore_aliases(self, data: Any) -> bool:
        return True


_Dumper.add_representer(
    FlowRecord,
    lambda dumper, data: dumper.represent_mapping(
        "tag:yaml.org,2002:map", data, flow_style=True
    ),
)


def flow_records(records: list | dict) -> list | dict:
    """
    Mark the records of a table to be written one per line.

    ``write_yaml`` then writes each item of the list (or each value of the
    dict) on one line, e.g. ``- {source: E, target: I, ...}``. For large tables
    a builder writes, such as thousands of connections; files people edit by
    hand stay in normal block style.

    Parameters
    ----------
    records
        A list of dicts, or a dict of dicts.

    Returns
    -------
    list or dict
        The same records, marked; pass them to :func:`write_yaml`, e.g.
        ``write_yaml(path, {"connections": flow_records(connections)})``.
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
    Write a dict as a YAML file.

    Parameters
    ----------
    path
        The file to write; its folder is created if needed.
    data
        The content. Fields passed through :func:`flow_records` are written one
        record per line, the rest in block style.
    header_comment
        Text written as ``#`` lines above the content, e.g. to say how the file
        was generated.
    """

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    text = yaml.dump(
        data, Dumper=_Dumper, sort_keys=False, default_flow_style=False, width=100_000
    )
    if header_comment:
        prefixed = "\n".join(f"# {line}" if line else "#" for line in header_comment.splitlines())
        text = f"{prefixed}\n{text}"

    path.write_text(text, encoding="utf-8")
