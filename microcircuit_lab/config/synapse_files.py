"""The synapses of a connection with ``rule: from_file``, read from its CSV file.

The file has one row per synapse and the columns ``source_index``,
``target_index``, ``weight`` and ``delay``, all required::

    source_index,target_index,weight,delay
    0,3,87.2,1.4
    0,10,91.0,0.9

An index counts the neurons of its population from 0. The weight is in the
connection's ``weight.unit`` (pA, nS or mV), the delay in ms. The connection
names the file in ``connectivity.yaml``, relative to the network folder
(``file: synapses/E_to_I.csv``).

A file can hold millions of rows, so its columns are read and checked as
whole numpy arrays (as in ``config/connection_table.py``), not row by row with
pydantic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

#: The columns of a synapse file and their types.
COLUMNS = {"source_index": "int64", "target_index": "int64", "weight": "float64", "delay": "float64"}


@dataclass(frozen=True, eq=False)
class SynapseList:
    """The synapses of one connection: one entry per synapse in each array."""

    source_index: np.ndarray
    target_index: np.ndarray
    weight: np.ndarray
    delay: np.ndarray

    def __len__(self) -> int:
        return len(self.weight)

    @classmethod
    def read_csv(cls, path: str | Path) -> SynapseList:
        """The synapses in a CSV file (see the module docstring)."""

        header = list(pd.read_csv(path, nrows=0).columns)
        if sorted(header) != sorted(COLUMNS):
            raise ValueError(f"{path}: the columns must be {', '.join(COLUMNS)}; found {', '.join(header)}.")
        try:
            frame = pd.read_csv(path, dtype=COLUMNS, keep_default_na=False, na_values=[""])
        except ValueError as error:
            # e.g. an empty cell or text in an index column
            raise ValueError(f"{path}: {error}") from None
        return cls(**{name: frame[name].to_numpy() for name in COLUMNS})

    def write_csv(self, path: str | Path) -> None:
        """Write the synapses as CSV, creating the folder if needed."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({name: getattr(self, name) for name in COLUMNS}).to_csv(path, index=False)

    def problems(self, n_source: int, n_target: int) -> list[str]:
        """What does not fit the populations it connects (``n_source`` and
        ``n_target`` neurons): no synapse at all, an index outside them, a
        weight that is not a number, a delay not above 0."""

        checks = [
            ("source_index", (self.source_index < 0) | (self.source_index >= n_source),
             f"must be from 0 to {n_source - 1} (the source population's neurons)"),
            ("target_index", (self.target_index < 0) | (self.target_index >= n_target),
             f"must be from 0 to {n_target - 1} (the target population's neurons)"),
            ("weight", ~np.isfinite(self.weight), "must be a number"),
            ("delay", ~(self.delay > 0), "must be greater than 0 (ms)"),
        ]
        if len(self) == 0:
            return ["no synapse: leave the connection out"]
        problems = []
        for name, rows, message in checks:
            if rows.any():
                # The line in the file, after the header.
                line = int(np.flatnonzero(rows)[0]) + 2
                more = f" (and {rows.sum() - 1} more rows)" if rows.sum() > 1 else ""
                problems.append(f"line {line}, {name}: {message}{more}")
        return problems


def read_synapse_lists(folder: Path, connections, where: str) -> dict[str, SynapseList]:
    """
    The synapses of each connection with ``rule: from_file``, by its
    ``file``, read from ``folder``. ``connections`` are the rows as written
    (dicts) or a ``ConnectionTable``; ``where`` names the file that lists them
    (e.g. ``connectivity.yaml``), for the error about a missing file. A row
    without its file is left to the checks of the connections.
    """

    if isinstance(connections, list):
        files = [row.get("file") for row in connections if isinstance(row, dict) and row.get("rule") == "from_file"]
    else:
        files = connections["file"][connections["rule"] == "from_file"].tolist()
    synapse_lists = {}
    for file in files:
        if not isinstance(file, str) or file in synapse_lists:
            continue
        path = folder / file
        if not path.is_file():
            raise FileNotFoundError(f"{folder}: {where} names file '{file}', but there is no file {path}.")
        synapse_lists[file] = SynapseList.read_csv(path)
    return synapse_lists
