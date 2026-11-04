"""write_network_directory: assemble in-memory parts into a valid,
on-disk configs/network/<name>/ directory."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml

from microcircuit_lab.builder_tools import (
    delay,
    weight,
    write_network_directory,
    zero_bound,
)
from microcircuit_lab.config.connection_table import ConnectionTable

NEURON = {
    "C_m": 250.0,
    "tau_m": 10.0,
    "tau_syn_ex": 0.5,
    "tau_syn_in": 0.5,
    "E_L": -65.0,
    "V_reset": -65.0,
    "V_th": -50.0,
    "t_ref": 2.0,
    "I_e": 0.0,
}


def _parts(tmp_path: Path, **overrides):
    """A minimal but complete set of write_network_directory arguments."""
    parts = dict(
        path=tmp_path / "net",
        populations=[
            {"name": "E", "size": 8, "neuron": "n", "initial_state": {"V_m": {"distribution": "normal", "mean": -65.0, "std": 5.0}}},
            {"name": "I", "size": 2, "neuron": "n", "initial_state": {"V_m": {"distribution": "normal", "mean": -65.0, "std": 5.0}}},
        ],
        neurons={"n": {"model": "iaf_psc_exp", "parameters": NEURON}},
        connections=[
            {"source": s, "target": t, "n_synapses": 20,
             "weight": weight(w, unit="pA", rel_std=0.1, **zero_bound(w, "redraw")),
             "delay": delay(1.5, rel_std=0.5, lower_bound=0.05, bound_mode="redraw")}
            for s, w in (("E", 87.8), ("I", -351.2))
            for t in ("E", "I")
        ],
        poisson_background={
            p: {"rate": 8.0, "indegree": 10, "weight": weight(87.8, unit="pA"), "delay": delay(1.5)}
            for p in ("E", "I")
        },
    )
    parts.update(overrides)
    return parts


def _load(tmp_path: Path, name: str) -> dict:
    return yaml.safe_load((tmp_path / "net" / name).read_text())


def test_writes_every_file_and_returns_the_validated_config(tmp_path: Path) -> None:
    config = write_network_directory(**_parts(tmp_path))

    # scaling, reference, stimuli and synapses are optional: not given, not written
    assert {p.name for p in (tmp_path / "net").glob("*.yaml")} == {
        "network.yaml", "populations.yaml", "neurons.yaml", "connectivity.yaml",
        "poisson_background.yaml",
    }
    assert set(config.populations) == {"E", "I"}
    assert config.populations["E"].size == 8
    assert config.scaling is None and config.reference is None


def test_manifest_uses_the_conventional_names(tmp_path: Path) -> None:
    write_network_directory(**_parts(tmp_path))

    assert _load(tmp_path, "network.yaml") == {
        "populations": "populations.yaml",
        "neurons": "neurons.yaml",
        "connectivity": "connectivity.yaml",
        "poisson_background": "poisson_background.yaml",
    }


def test_stimuli_adds_both_the_file_and_the_manifest_key(tmp_path: Path) -> None:
    write_network_directory(
        **_parts(tmp_path, stimuli=[{"type": "dc", "targets": ["E"], "amplitude": 100.0}])
    )

    assert (tmp_path / "net" / "stimuli.yaml").exists()
    assert _load(tmp_path, "network.yaml")["stimuli"] == "stimuli.yaml"


def test_reference_takes_the_inner_rate_map(tmp_path: Path) -> None:
    write_network_directory(**_parts(tmp_path, reference={"E": 5.0, "I": 7.0}))

    assert _load(tmp_path, "reference.yaml") == {"full_mean_rates": {"E": 5.0, "I": 7.0}}


def test_big_tables_are_written_one_record_per_line(tmp_path: Path) -> None:
    write_network_directory(**_parts(tmp_path))

    assert "- {source:" in (tmp_path / "net" / "connectivity.yaml").read_text()


def test_compact_false_writes_block_style_with_the_same_content(tmp_path: Path) -> None:
    compact = write_network_directory(**_parts(tmp_path / "compact"))
    block = write_network_directory(**_parts(tmp_path / "block"), compact=False)

    assert "- name:" in (tmp_path / "block" / "net" / "populations.yaml").read_text()
    assert "- {source:" in (tmp_path / "block" / "net" / "connectivity.yaml").read_text()
    assert block == compact


def test_a_connection_table_is_written_with_its_default_values(tmp_path: Path) -> None:
    parts = _parts(tmp_path)
    parts["connections"] = ConnectionTable.from_yaml_rows(parts["connections"])
    network = write_network_directory(**parts)

    columns = set(pd.read_csv(parts["path"] / "connections.csv", nrows=0).columns)
    assert {"rule", "weight.distribution", "delay.distribution"} <= columns
    # a column no row sets is left out
    assert "synapse" not in columns
    assert network.connections == parts["connections"]


def test_an_invalid_part_raises_with_the_field_named(tmp_path: Path) -> None:
    parts = _parts(tmp_path)
    parts["populations"][0]["size"] = -1

    with pytest.raises(ValueError, match="populations.yaml"):
        write_network_directory(**parts)
