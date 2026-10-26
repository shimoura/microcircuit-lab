"""The on-disk network-config schema and the load_network check."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from microcircuit_lab.config.network import NetworkDirectory, NetworkManifest
from microcircuit_lab.network.load import load_network, read_network_files

TOY = Path("configs/network/toy")
NETWORK_CONFIGS = sorted(
    path.parent for path in Path("configs/network").glob("*/network.yaml")
)


@pytest.mark.parametrize("network_config", NETWORK_CONFIGS, ids=lambda path: path.name)
def test_every_network_config_in_the_repository_is_valid(network_config: Path) -> None:
    """The core reads every network config under configs/network, however
    it was written: by hand or by a builder."""
    assert load_network(network_config).populations


@pytest.fixture
def network_dir(tmp_path: Path) -> Path:
    """A private, editable copy of the toy network."""
    dst = tmp_path / "net"
    shutil.copytree(TOY, dst)
    return dst


def _edit_yaml(path: Path, mutate) -> None:
    data = yaml.safe_load(path.read_text())
    mutate(data)
    path.write_text(yaml.safe_dump(data))


# -----------------------------------------------------------------------------
# read_network_files checks every file against the models in microcircuit_lab.config
# -----------------------------------------------------------------------------
def test_toy_directory_matches_the_schema() -> None:
    directory = read_network_files(TOY)

    assert isinstance(directory, NetworkDirectory)
    assert {p.name for p in directory.populations.populations} == {"E", "I"}
    assert set(directory.neurons.neurons) == {"excitatory", "inhibitory"}
    assert directory.background_inputs.background_mode == "poisson"
    assert directory.stimuli.stimuli == []


def test_unknown_field_is_rejected(network_dir: Path) -> None:
    _edit_yaml(
        network_dir / "populations.yaml",
        lambda d: d["populations"][0].__setitem__("siz", 800),
    )
    with pytest.raises(ValueError, match="siz"):
        read_network_files(network_dir)


def test_unknown_stimulus_type_points_to_where_new_ones_are_added(network_dir: Path) -> None:
    (network_dir / "stimuli.yaml").write_text(
        "stimuli:\n  - {type: spike, targets: [E], spike_times: [500.0]}\n"
    )
    _edit_yaml(network_dir / "network.yaml", lambda d: d.__setitem__("stimuli", "stimuli.yaml"))
    with pytest.raises(ValueError, match="Changing the core") as error:
        read_network_files(network_dir)
    assert "stimuli.yaml: stimuli.0" in str(error.value)


def test_unknown_distribution_is_a_project_one_that_nest_rejects(network_dir: Path) -> None:
    from microcircuit_lab.backends.nest.simulator import NestBackend
    from microcircuit_lab.config.simulation import SimulationConfig

    _edit_yaml(
        network_dir / "connectivity.yaml",
        lambda d: d["connections"][0]["delay"].__setitem__("distribution", "gamma"),
    )
    network = load_network(network_dir)
    with pytest.raises(ValueError, match="NEST has no delay distribution 'gamma'.*not project distributions"):
        NestBackend(network, SimulationConfig()).check()


def test_other_errors_do_not_point_to_contributing(network_dir: Path) -> None:
    _edit_yaml(
        network_dir / "populations.yaml",
        lambda d: d["populations"][0].__setitem__("size", -1),
    )
    with pytest.raises(ValueError) as error:
        read_network_files(network_dir)
    assert "CONTRIBUTING" not in str(error.value)


def test_error_names_the_file_and_the_field(network_dir: Path) -> None:
    _edit_yaml(
        network_dir / "populations.yaml",
        lambda d: d["populations"][0].__setitem__("size", -1),
    )
    with pytest.raises(ValueError) as error:
        read_network_files(network_dir)

    message = str(error.value)
    assert str(network_dir) in message
    assert "populations.yaml: populations.0.size" in message


def test_neuron_parameters_stay_open(network_dir: Path) -> None:
    # A neuron model may take parameters this framework has never heard of;
    # the simulator backend is the authority on those names, not the schema.
    _edit_yaml(
        network_dir / "neurons.yaml",
        lambda d: d["neurons"]["excitatory"]["parameters"].__setitem__("g_L", 25.0),
    )
    directory = read_network_files(network_dir)
    assert directory.neurons.neurons["excitatory"].parameters.model_dump()["g_L"] == 25.0


def test_manifest_rejects_an_unknown_file_key() -> None:
    with pytest.raises(ValidationError, match="extra"):
        NetworkManifest.model_validate(
            {
                "populations": "populations.yaml",
                "neurons": "neurons.yaml",
                "connectivity": "connectivity.yaml",
                "background_inputs": "background_inputs.yaml",
                "scaling": "scaling.yaml",
                "reference": "reference.yaml",
                "extras": "extras.yaml",
            }
        )


# -----------------------------------------------------------------------------
# load_network: schema + cross-file refs + prepare_network dry run
# -----------------------------------------------------------------------------


def test_validate_catches_a_dangling_neuron_reference(network_dir: Path) -> None:
    _edit_yaml(
        network_dir / "populations.yaml",
        lambda d: d["populations"][0].__setitem__("neuron", "nope"),
    )
    with pytest.raises(ValueError, match="nope"):
        load_network(network_dir)


def test_validate_catches_a_connection_to_an_undefined_population(network_dir: Path) -> None:
    _edit_yaml(
        network_dir / "connectivity.yaml",
        lambda d: d["connections"][0].__setitem__("target", "Z"),
    )
    with pytest.raises(ValueError, match="'Z'"):
        load_network(network_dir)


def test_validate_catches_two_entries_for_the_same_pair(network_dir: Path) -> None:
    _edit_yaml(
        network_dir / "connectivity.yaml",
        lambda d: d["connections"].append(d["connections"][0]),
    )
    with pytest.raises(ValueError, match="more than one entry"):
        load_network(network_dir)


def test_validate_catches_a_background_input_for_an_undefined_population(
    network_dir: Path,
) -> None:
    _edit_yaml(
        network_dir / "background_inputs.yaml",
        lambda d: d["background_inputs"].__setitem__("Z", d["background_inputs"]["E"]),
    )
    with pytest.raises(ValueError, match="'Z'"):
        load_network(network_dir)
