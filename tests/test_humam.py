"""Tests for HuMAM configuration generation."""

from pathlib import Path

import pytest
import yaml

# The HuMAM builder is a bundled example, not part of the core: skip these
# tests if a fork removes it.
generate_humam_configs = pytest.importorskip("builders.humam").generate_humam_configs


def test_generate_single_area_uses_bare_population_names(tmp_path: Path) -> None:
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


def test_single_area_defaults_to_missing_area_compensation(tmp_path: Path) -> None:
    paths = generate_humam_configs(
        area="bankssts",
        config_dir=tmp_path,
        network_name="humam_test",
        simulation_name="humam_test",
    )

    assert paths["other_area_count"] > 0
    assert paths["missing_area_compensation_applied"] is True

    neurons_path = paths["network_dir"] / "neurons.yaml"
    text = neurons_path.read_text()
    assert text.startswith("# Compensated for")

    neurons = yaml.safe_load(text)["neurons"]
    populations = yaml.safe_load((paths["network_dir"] / "populations.yaml").read_text())

    # One neuron definition per population (not two shared ones), each
    # with its own nonzero compensation current, referenced by name.
    pop_names = {p["name"] for p in populations["populations"]}
    assert set(neurons) == pop_names
    assert all(neurons[name]["parameters"]["I_e"] != 0.0 for name in pop_names)
    assert all(p["neuron"] == p["name"] for p in populations["populations"])


def test_single_area_compensation_can_be_disabled(tmp_path: Path) -> None:
    paths = generate_humam_configs(
        area="bankssts",
        config_dir=tmp_path,
        network_name="humam_test",
        simulation_name="humam_test",
        compensate_missing_areas=False,
    )

    assert paths["missing_area_compensation_applied"] is False

    neurons_path = paths["network_dir"] / "neurons.yaml"
    text = neurons_path.read_text()
    assert text.startswith("# WARNING")

    neurons = yaml.safe_load(text)["neurons"]
    # Falls back to the original two shared neuron definitions, I_e untouched.
    assert set(neurons) == {"excitatory", "inhibitory"}
    assert neurons["excitatory"]["parameters"]["I_e"] == 0.0
    assert neurons["inhibitory"]["parameters"]["I_e"] == 0.0


def test_multi_area_has_no_missing_area_compensation(tmp_path: Path) -> None:
    """area='all' includes every area, so there's nothing to compensate for."""

    paths = generate_humam_configs(
        area="all",
        config_dir=tmp_path,
        network_name="humam_all_test",
        simulation_name="humam_all_test",
    )

    assert paths["other_area_count"] == 0
    assert paths["missing_area_compensation_applied"] is False

    neurons_path = paths["network_dir"] / "neurons.yaml"
    assert not neurons_path.read_text().startswith("#")
