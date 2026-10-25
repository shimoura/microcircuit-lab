"""All connections of a network as one table, one column per field.

``connectivity.py`` describes one connection (``ConnectionConfig``: its
fields, limits and defaults). This module holds all connections of a network
together, as columns: a large network (e.g. a multi-area model) can have
millions of connections, and a step that changes them (e.g. every weight
divided by ``sqrt(K_scaling)``) then changes a whole column at once, with no
loop over rows and no Python object per row.

Each column is checked with pydantic against its field in ``ConnectionConfig``,
so a connection is described in one place only.

A large network can keep its connections in a CSV file, named by
``connections_file`` in ``connectivity.yaml``, with the same columns. There the
rule's number goes under its own name (``n_synapses``, ``indegree``,
``outdegree`` or ``p``), as in the YAML file, the ``parameters`` of a project
rule or distribution are written as JSON text (``{"width": 10}``), and a column
with a default can be left out.
"""

from __future__ import annotations

import functools
import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Annotated, Any

import numpy as np
import pandas as pd
from pydantic import TypeAdapter, ValidationError
from pydantic.fields import FieldInfo

from microcircuit_lab.config.connectivity import (
    RULE_NUMBER,
    SHARED_DISTRIBUTIONS,
    SHARED_RULES,
    ConnectionConfig,
    DelayDistribution,
    WeightDistribution,
)

# Column name: how its values are stored. The names are the paths of the
# fields in a connectivity.yaml row; ``number`` is the number the row's rule
# takes (n_synapses, indegree, outdegree or p; NaN for a rule that takes none).
COLUMNS = {
    "source": "text",
    "target": "text",
    "rule": "text",
    "number": "number",
    "parameters": "parameters",
    "allow_autapses": "yes/no",
    "allow_multapses": "yes/no",
    "synapse": "text",
    "weight.mean": "number",
    "weight.rel_std": "number",
    "weight.distribution": "text",
    "weight.parameters": "parameters",
    "weight.unit": "text",
    "delay.mean": "number",
    "delay.rel_std": "number",
    "delay.distribution": "text",
    "delay.parameters": "parameters",
    "delay.minimum": "number",
}
PARAMETER_COLUMNS = [column for column, kind in COLUMNS.items() if kind == "parameters"]


def _check_every_field_has_a_column() -> None:
    """A field of ConnectionConfig (or of its weight or delay) without a column
    would be lost when rows become a table: fail as soon as the module loads."""

    fields = [f"{group}.{name}" for group, model in (("weight", WeightDistribution),
                                                      ("delay", DelayDistribution))
              for name in model.model_fields]
    fields += [name for name in ConnectionConfig.model_fields
               if name not in ("weight", "delay", *RULE_NUMBER.values())]
    missing = [name for name in fields if name not in COLUMNS]
    if missing:
        raise RuntimeError(f"connection field(s) {missing} have no column: add them to COLUMNS.")


def _field(column: str) -> FieldInfo:
    """The field of ``ConnectionConfig`` (or of its weight or delay) behind a column."""
    group, _, name = column.rpartition(".")
    model = {"": ConnectionConfig, "weight": WeightDistribution, "delay": DelayDistribution}[group]
    return model.model_fields[name]


_check_every_field_has_a_column()


class ConnectionTable:
    """
    The connections of a network, one row per connection, held as columns.

    ``table["weight.mean"]`` is a column, a read-only numpy array. A table
    never changes once made: :meth:`with_columns` and :meth:`keep_rows`
    return a new one.
    """

    def __init__(self, columns: Mapping[str, Any], *, copy: bool = True) -> None:
        """
        Parameters
        ----------
        columns
            ``{column name: values}``, one value per connection. A column
            with a default in ``ConnectionConfig`` can be left out.
        copy
            Copy the arrays given, so changing them later cannot change the
            table. ``False`` for arrays that nothing else holds (saves a copy
            of each column of a large table).
        """
        self._columns = _fill_defaults(columns, copy)
        _check_columns(self._columns, COLUMNS)

    # Making and writing -----------------------------------------------------

    @classmethod
    def from_yaml_rows(cls, rows: Iterable[ConnectionConfig | Mapping[str, Any]]) -> ConnectionTable:
        """A table from the rows of ``connectivity.yaml`` (dicts, or
        ``ConnectionConfig`` objects already checked)."""

        rows = [row if isinstance(row, ConnectionConfig) else ConnectionConfig.model_validate(row)
                for row in rows]
        return cls({column: [_value(row, column) for row in rows] for column in COLUMNS}, copy=False)

    @classmethod
    def read_csv(cls, path: str | Path) -> ConnectionTable:
        """A table from a CSV file (see the module docstring for its columns)."""

        # Every setting written out: pandas' defaults would round the last digit
        # of numbers, read text such as "NA" or "None" as missing, and guess the
        # type of each column. Here only an empty cell is "not set", and each
        # column has the type COLUMNS gives it (text read as categories: one
        # string per distinct name, not one per row).
        types = {"text": "category", "yes/no": "boolean", "number": "float64", "parameters": "category"}
        dtype = {column: types[kind] for column, kind in COLUMNS.items() if column != "number"}
        dtype.update({name: "float64" for name in RULE_NUMBER.values()})
        frame = pd.read_csv(path, dtype=dtype, float_precision="round_trip",
                            keep_default_na=False, na_values=[""])
        if "number" in frame.columns:
            raise ValueError(f"{path}: no column 'number' in a file; give each rule's number "
                             f"under its name, one of {list(RULE_NUMBER.values())}.")
        columns = {name: _csv_column(frame[name]) for name in frame.columns}
        for name in PARAMETER_COLUMNS:
            if name in columns:
                columns[name] = _parameters_from_json(columns[name], name, path)

        # The rule's number, from the column named after the rule.
        rule = columns.get("rule", _field("rule").default)
        takes_number = np.broadcast_to(np.isin(rule, list(RULE_NUMBER)), (len(frame),))
        if takes_number.any() and not any(name in columns for name in RULE_NUMBER.values()):
            raise ValueError(f"{path}: no column for the number of the rule; add one of "
                             f"{list(RULE_NUMBER.values())}.")
        number = np.full(len(frame), np.nan)
        for rule_name, name in RULE_NUMBER.items():
            if name in columns:
                rows = np.broadcast_to(rule == rule_name, number.shape)
                values = np.asarray(columns.pop(name), dtype=float)
                # A number under another rule's name would be lost: refuse it.
                misplaced = np.flatnonzero(~rows & ~np.isnan(values))
                if misplaced.size:
                    i = misplaced[0]
                    found = rule[i] if isinstance(rule, np.ndarray) else rule
                    raise ValueError(f"{path}: line {i + 2}, {name}: set, but the rule is {found}.")
                number[rows] = values[rows]
        columns["number"] = number

        try:
            return cls(columns, copy=False)  # arrays made here, held by nothing else
        except ValueError as error:
            # "connections.12.p" -> "line 14, p": the line in the file, after the header.
            message = re.sub(r"connections\.(\d+)\.", lambda m: f"line {int(m[1]) + 2}, ", str(error))
            raise ValueError(f"{path}: {message}") from error

    def write_csv(self, path: str | Path) -> None:
        """Write the table as CSV: the rule's number under its own name, and a
        column with a default only where some row differs from it."""

        frame = pd.DataFrame(self._columns)
        for rule, name in RULE_NUMBER.items():
            rows = frame["rule"] == rule
            if rows.any():
                values = frame["number"].where(rows)
                frame[name] = values if name == "p" else values.astype("Int64")
        frame = frame.drop(columns="number")
        for name in PARAMETER_COLUMNS:
            frame[name] = [None if v is None else json.dumps(v) for v in frame[name]]
        for column in COLUMNS:
            field = _field(column) if column != "number" else None
            if field is None or field.is_required():
                continue
            if field.default is None:
                all_default = frame[column].isna().all()
            else:
                all_default = (frame[column] == field.default).all()
            if all_default:
                frame = frame.drop(columns=column)
        frame.to_csv(path, index=False)

    def to_yaml_rows(self) -> list[dict[str, Any]]:
        """The rows as ``connectivity.yaml`` writes them: nested dicts, the
        rule's number under its own name, fields that are not set left out."""

        columns = {column: self._columns[column].tolist() for column in COLUMNS}
        rows = []
        for i in range(len(self)):
            row: dict[str, Any] = {}
            for column, values in columns.items():
                value = values[i]
                if column == "number":
                    name = RULE_NUMBER.get(columns["rule"][i])
                    if name is not None:
                        row[name] = value if name == "p" else int(value)
                elif not _is_unset(value):
                    group, _, name = column.rpartition(".")
                    (row.setdefault(group, {}) if group else row)[name] = value
            rows.append(row)
        return rows

    # Reading ----------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._columns["source"])

    def __getitem__(self, column: str) -> np.ndarray:
        """A column, e.g. ``table["weight.mean"]``."""
        return self._columns[column]

    def population_index(self, column: str, names: list[str]) -> np.ndarray:
        """For ``column`` "source" or "target": each row's population as its
        position in ``names``."""

        # pandas finds the distinct names by hashing; numpy would sort millions of strings.
        codes, labels = pd.factorize(self._columns[column])
        position = {name: i for i, name in enumerate(names)}
        return np.asarray([position[label] for label in labels], dtype=np.int64)[codes]

    def duplicates(self, columns: list[str]) -> list[tuple]:
        """The combinations of values in ``columns`` found in more than one row."""

        # pandas finds repeated rows by hashing them.
        frame = pd.DataFrame({column: self._columns[column] for column in columns})
        doubled = frame[frame.duplicated(keep=False)].drop_duplicates()
        return [tuple(None if _is_unset(v) else v for v in row)
                for row in doubled.itertuples(index=False)]

    # A new table ------------------------------------------------------------

    def with_columns(self, *, copy: bool = True, **columns: Any) -> ConnectionTable:
        """A copy with these columns replaced; only they are checked again.
        For a name with a dot, pass a dict: ``with_columns(**{"weight.mean": values})``.
        ``copy=False`` for arrays that nothing else holds (see :class:`ConnectionTable`)."""

        unknown = [name for name in columns if name not in COLUMNS]
        if unknown:
            raise ValueError(f"unknown connection column(s) {unknown}.")
        table = ConnectionTable.__new__(ConnectionTable)
        table._columns = {**self._columns,
                          **{name: _as_column(name, values, copy) for name, values in columns.items()}}
        changed = set(columns) | ({"number"} if "rule" in columns else set())
        _check_columns(table._columns, changed)
        return table

    def keep_rows(self, keep: np.ndarray) -> ConnectionTable:
        """A copy with only the rows where ``keep`` is true."""

        keep = np.asarray(keep, dtype=bool)
        table = ConnectionTable.__new__(ConnectionTable)
        table._columns = {column: _read_only(values[keep]) for column, values in self._columns.items()}
        return table

    # The table never changes, so a copy can be the table itself.
    def __copy__(self) -> ConnectionTable:
        return self

    def __deepcopy__(self, memo) -> ConnectionTable:
        return self

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ConnectionTable):
            return NotImplemented
        return len(self) == len(other) and all(
            np.array_equal(self[c], other[c], equal_nan=COLUMNS[c] == "number") for c in COLUMNS
        )

    def __repr__(self) -> str:
        return f"ConnectionTable({len(self)} connections)"


def to_connection_table(value: Any) -> ConnectionTable:
    """A table as it is, or a table made from the rows of connectivity.yaml."""
    return value if isinstance(value, ConnectionTable) else ConnectionTable.from_yaml_rows(value)


def _value(row: ConnectionConfig, column: str) -> Any:
    """The value of ``column`` in one row."""
    if column == "number":
        return row.number
    group, _, name = column.rpartition(".")
    return getattr(getattr(row, group) if group else row, name)


def _fill_defaults(columns: Mapping[str, Any], copy: bool) -> dict[str, np.ndarray]:
    """Every column as a read-only array (see :func:`_as_column`); a left-out
    column gets its field's default."""

    unknown = [name for name in columns if name not in COLUMNS]
    if unknown:
        raise ValueError(f"unknown connection column(s) {unknown}; the columns are {list(COLUMNS)}.")
    n = len(columns["source"]) if "source" in columns else 0

    filled = {}
    for column in COLUMNS:
        if column in columns:
            filled[column] = _as_column(column, columns[column], copy)
        elif column != "number" and not _field(column).is_required():
            filled[column] = _as_column(column, [_field(column).default] * n, copy=False)
        else:
            raise ValueError(f"the connections have no column {column!r}.")
    return filled


def _as_column(column: str, values: Any, copy: bool) -> np.ndarray:
    """One column as a read-only numpy array: numbers as floats (NaN where
    not set), text and yes/no as Python objects (None where not set). With
    ``copy``, never the array given (see :class:`ConnectionTable`)."""

    make = np.array if copy else np.asarray
    return _read_only(make(values, dtype=float if COLUMNS[column] == "number" else object))


def _check_columns(columns: dict[str, np.ndarray], which: Iterable[str]) -> None:
    """Check the columns named in ``which`` with pydantic, each against its
    field in ``ConnectionConfig``; the number against the field of each row's
    rule (n_synapses, ..., p). Raises one error listing every column with a
    problem, e.g. ``connections.12.weight.rel_std: Input should be greater
    than or equal to 0``."""

    problems = []
    for column in which:
        if column != "number":
            problems += _problems(column, columns[column], _checker(column))
    if "number" in which:
        for rule, name in RULE_NUMBER.items():
            rows = np.flatnonzero(columns["rule"] == rule)
            if rows.size:
                problems += _problems(name, columns["number"][rows], _checker(name, required=True), rows)
    if {"rule", "number", *PARAMETER_COLUMNS, "weight.distribution", "delay.distribution"} & set(which):
        problems += _rule_problems(columns)
    if problems:
        raise ValueError("\n".join(problems))


def _rule_problems(columns: dict[str, np.ndarray]) -> list[str]:
    """A number for a rule that takes none, or parameters for a shared rule or
    distribution."""

    def given(column: str) -> np.ndarray:
        return np.array([value is not None for value in columns[column]], dtype=bool)

    rule = columns["rule"]
    checks = [
        ("rule", ~np.isin(rule, list(RULE_NUMBER)) & ~np.isnan(columns["number"]), "takes no number"),
        ("rule", np.isin(rule, SHARED_RULES) & given("parameters"), "takes no parameters"),
    ]
    for group in ("weight", "delay"):
        shared = np.isin(columns[f"{group}.distribution"], SHARED_DISTRIBUTIONS)
        checks.append((f"{group}.distribution", shared & given(f"{group}.parameters"), "takes no parameters"))
    problems = []
    for column, rows, what in checks:
        if rows.any():
            i = int(np.flatnonzero(rows)[0])
            problems.append(f"connections.{i}.{column}: {columns[column][i]!r} {what} (only a project one does)")
    return problems


def _parameters_from_json(values: np.ndarray, column: str, path: str | Path) -> np.ndarray:
    """A parameters column of a CSV file: each cell's JSON text as a dict.
    Each distinct text is parsed once, and its rows share the dict."""

    parsed = np.empty(len(values), dtype=object)
    known: dict[str | None, dict | None] = {None: None}
    for i, text in enumerate(values):
        if text not in known:
            try:
                known[text] = json.loads(text)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}: line {i + 2}, {column}: not JSON ({error.msg}): {text}") from None
        parsed[i] = known[text]
    return parsed


@functools.cache
def _checker(column: str, required: bool = False) -> TypeAdapter:
    """A pydantic check of a whole column, against the field behind it (a
    column name, or the name of a rule's number such as ``p``). With
    ``required``, ``None`` is refused even if the field allows it. Made once
    per column, then reused."""

    field = ConnectionConfig.model_fields[column] if column in RULE_NUMBER.values() else _field(column)
    annotation = field.annotation
    if required:
        annotation = int if annotation == int | None else float
    if field.metadata:
        annotation = Annotated[(annotation, *field.metadata)]
    return TypeAdapter(list[annotation])


def _problems(name: str, values: np.ndarray, checker: TypeAdapter, rows=None) -> list[str]:
    """The first problem pydantic finds in a column, and how many rows have one."""

    values = values.tolist()
    if isinstance(values[0] if values else None, float):
        values = [None if v != v else v for v in values]  # NaN (not set) as None
    try:
        checker.validate_python(values)
    except ValidationError as error:
        errors = error.errors()
        i = errors[0]["loc"][0]
        row = rows[i] if rows is not None else i
        more = f" (and {len(errors) - 1} more rows)" if len(errors) > 1 else ""
        return [f"connections.{row}.{name}: {errors[0]['msg']}{more}"]
    return []


def _csv_column(column: pd.Series) -> np.ndarray:
    """A column read by pandas as a numpy array, ``None`` (text, yes/no) or
    NaN (numbers) where the cell is empty. Text keeps one string object per
    distinct value, shared by its rows, rather than one per row."""
    if isinstance(column.dtype, pd.CategoricalDtype):
        labels = np.append(np.asarray(column.cat.categories, dtype=object), None)
        return labels[column.cat.codes.to_numpy()]  # code -1 (empty cell) picks None
    if column.dtype == "boolean":
        return column.to_numpy(dtype=object, na_value=None)
    return column.to_numpy()


def _read_only(values: np.ndarray) -> np.ndarray:
    """A read-only view, so a table's columns cannot be changed in place."""
    view = values.view()
    view.flags.writeable = False
    return view


def _is_unset(value: Any) -> bool:
    return value is None or (isinstance(value, float) and np.isnan(value))
