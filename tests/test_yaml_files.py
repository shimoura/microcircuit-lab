"""Tests for the YAML read/write helpers (yaml_files)."""

from pathlib import Path

from microcircuit_lab.yaml_files import flow_records, read_yaml, write_yaml


def test_write_yaml_roundtrips_through_read_yaml(tmp_path: Path) -> None:
    path = tmp_path / "data.yaml"
    data = {"a": 1, "b": {"c": [1, 2, 3]}}

    write_yaml(path, data)

    assert read_yaml(path) == data


def test_flow_records_list_is_one_line_per_record(tmp_path: Path) -> None:
    path = tmp_path / "connections.yaml"
    records = [{"source": "E", "target": "E", "weight": {"mean": 0.1}}]

    write_yaml(path, {"connections": flow_records(records)})

    lines = path.read_text().splitlines()
    assert lines == [
        "connections:",
        "- {source: E, target: E, weight: {mean: 0.1}}",
    ]
    assert read_yaml(path) == {"connections": records}


def test_flow_records_dict_is_one_line_per_value(tmp_path: Path) -> None:
    path = tmp_path / "background_inputs.yaml"
    records = {"E": {"rate": 8.0}, "I": {"rate": 8.0}}

    write_yaml(path, {"background_inputs": flow_records(records)})

    lines = path.read_text().splitlines()
    assert lines == ["background_inputs:", "  E: {rate: 8.0}", "  I: {rate: 8.0}"]
    assert read_yaml(path) == {"background_inputs": records}


def test_header_comment_is_prefixed_and_parses_as_comments(tmp_path: Path) -> None:
    path = tmp_path / "neurons.yaml"

    write_yaml(path, {"neurons": {}}, header_comment="line one\n\nline three")

    text = path.read_text()
    assert text.startswith("# line one\n#\n# line three\n")
    assert read_yaml(path) == {"neurons": {}}  # comments don't affect parsed content


def test_no_header_comment_by_default(tmp_path: Path) -> None:
    path = tmp_path / "plain.yaml"

    write_yaml(path, {"a": 1})

    assert not path.read_text().startswith("#")
