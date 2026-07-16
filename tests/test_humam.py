"""Tests for HuMAM configuration generation."""

from pathlib import Path

import yaml

from microcircuit_lab.models.humam import generate_humam_configs


def test_generate_single_area_configs(tmp_path: Path) -> None:
    paths = generate_humam_configs(
        area="bankssts",
        config_dir=tmp_path,
        network_name="humam_test",
        simulation_name="humam_test",
    )

    network_dir = paths["network_dir"]
    connectivity = yaml.safe_load((network_dir / "connectivity.yaml").read_text())
    populations = yaml.safe_load((network_dir / "populations.yaml").read_text())

    assert populations["populations"]
    assert connectivity["connections"]
    assert all(c["n_synapses"] > 0 for c in connectivity["connections"])
    assert all("__" not in p["name"] for p in populations["populations"])


def test_generate_multi_area_uses_area_qualified_names(tmp_path: Path) -> None:
    paths = generate_humam_configs(
        area="all",
        config_dir=tmp_path,
        network_name="humam_all_test",
        simulation_name="humam_all_test",
    )

    network_dir = paths["network_dir"]
    populations = yaml.safe_load((network_dir / "populations.yaml").read_text())
    names = [p["name"] for p in populations["populations"]]

    assert names
    assert all("__" in name for name in names)
