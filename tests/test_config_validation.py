"""The on-disk network-config schema and the validate_network_config check."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from microcircuit_lab.config.files import NetworkDirectory, NetworkManifest
from microcircuit_lab.io.files import read_network_directory
from microcircuit_lab.io.network_validation import validate_network_config

TOY = Path("configs/network/toy")


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
# schema: read_network_directory validates every file against config.files
# -----------------------------------------------------------------------------
def test_toy_directory_matches_the_schema() -> None:
    directory = read_network_directory(TOY)

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
    with pytest.raises(ValidationError, match="siz"):
        read_network_directory(network_dir)


def test_missing_required_field_is_rejected(network_dir: Path) -> None:
    _edit_yaml(
        network_dir / "populations.yaml",
        lambda d: d["populations"][0].pop("size"),
    )
    with pytest.raises(ValidationError, match="size"):
        read_network_directory(network_dir)


def test_wrong_type_is_rejected(network_dir: Path) -> None:
    _edit_yaml(
        network_dir / "connectivity.yaml",
        lambda d: d["connections"][0].__setitem__("n_synapses", "lots"),
    )
    with pytest.raises(ValidationError, match="n_synapses"):
        read_network_directory(network_dir)


def test_neuron_parameters_stay_open(network_dir: Path) -> None:
    # A neuron model may take parameters this framework has never heard of;
    # the simulator backend is the authority on those names, not the schema.
    _edit_yaml(
        network_dir / "neurons.yaml",
        lambda d: d["neurons"]["excitatory"]["parameters"].__setitem__("g_L", 25.0),
    )
    directory = read_network_directory(network_dir)
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
# validate_network_config: schema + cross-file refs + preprocessing dry run
# -----------------------------------------------------------------------------
def test_validate_passes_on_the_toy_network() -> None:
    config = validate_network_config(TOY)

    assert set(config.populations) == {"E", "I"}
    assert config.connections


def test_validate_catches_a_dangling_neuron_reference(network_dir: Path) -> None:
    _edit_yaml(
        network_dir / "populations.yaml",
        lambda d: d["populations"][0].__setitem__("neuron", "nope"),
    )
    with pytest.raises(ValueError, match="nope"):
        validate_network_config(network_dir)


def test_validate_catches_a_connection_to_an_undefined_population(network_dir: Path) -> None:
    _edit_yaml(
        network_dir / "connectivity.yaml",
        lambda d: d["connections"][0].__setitem__("target", "Z"),
    )
    with pytest.raises(ValueError, match="'Z'"):
        validate_network_config(network_dir)


def test_validate_catches_a_background_input_for_an_undefined_population(
    network_dir: Path,
) -> None:
    _edit_yaml(
        network_dir / "background_inputs.yaml",
        lambda d: d["background_inputs"].__setitem__("Z", d["background_inputs"]["E"]),
    )
    with pytest.raises(ValueError, match="'Z'"):
        validate_network_config(network_dir)
