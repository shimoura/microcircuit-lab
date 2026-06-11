"""
Utilities for reading configuration files.

This module intentionally performs no interpretation of the configuration.
It only reads YAML files and returns plain Python dictionaries.

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
            f"Expected top-level mapping in '{path}', "
            f"got {type(data).__name__}."
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

    return NetworkFiles(
        populations=read_yaml(path / "populations.yaml"),
        neurons=read_yaml(path / "neurons.yaml"),
        connectivity=read_yaml(path / "connectivity.yaml"),
        inputs=read_yaml(path / "inputs.yaml"),
        scaling=read_yaml(path / "scaling.yaml"),
    )

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