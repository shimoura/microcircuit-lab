"""The jiang24_stp builder: its analysis files, and the Base model of jiang24 with
STP synapses, scaled weights and other background rates, and nothing else changed."""

import pytest

from builders.jiang24 import generate_jiang24
from builders.jiang24_stp import data, generate_jiang24_stp
from builders.jiang24_stp.build import stp_key
from microcircuit_lab.config.yaml_files import read_yaml


@pytest.fixture(scope="module")
def configs(tmp_path_factory):
    folder = tmp_path_factory.mktemp("configs")
    generate_jiang24(config_dir=folder)
    generate_jiang24_stp(config_dir=folder)
    return folder


def _read(configs, network, file):
    return read_yaml(configs / "network" / network / file)


def test_fig6_analysis(configs):
    default = read_yaml(configs / "analysis" / "jiang24_stp.yaml")
    fig6 = read_yaml(configs / "analysis" / "jiang24_stp_fig6.yaml")

    assert set(default) == {"style"}
    assert fig6 == read_yaml(configs / "analysis" / "jiang24_fig6.yaml")


def test_only_stp_weights_and_background_differ_from_jiang24(configs):
    for file in ("populations.yaml", "neurons.yaml"):
        assert _read(configs, "jiang24_stp", file) == _read(configs, "jiang24", file)
    assert read_yaml(configs / "simulation" / "jiang24_stp.yaml") == read_yaml(configs / "simulation" / "jiang24.yaml")

    stp = _read(configs, "jiang24_stp", "connectivity.yaml")["connections"]
    static = _read(configs, "jiang24", "connectivity.yaml")["connections"]
    assert len(stp) == len(static)
    names = [name for name, _, _ in data.populations]
    for connection, base in zip(stp, static):
        factor = data.weight_factors[names.index(connection["target"])][names.index(connection["source"])]
        # A projection has STP exactly when its weight is scaled.
        assert ("synapse" in connection) == (factor != 1.0)
        assert connection["weight"]["mean"] == pytest.approx(factor * base["weight"]["mean"])
        assert connection["weight"]["std"] == abs(connection["weight"]["mean"])
        rest = {key: value for key, value in connection.items() if key not in ("synapse", "weight")}
        assert rest == {key: value for key, value in base.items() if key != "weight"}

    stp_background = _read(configs, "jiang24_stp", "poisson_background.yaml")["poisson_background"]
    static_background = _read(configs, "jiang24", "poisson_background.yaml")["poisson_background"]
    for population, background in stp_background.items():
        assert background["rate"] == data.bg_rate[population.split("_")[1]]
        assert {**background, "rate": None} == {**static_background[population], "rate": None}


def test_stp_synapses(configs):
    synapses = _read(configs, "jiang24_stp", "synapses.yaml")["synapses"]
    by_pair = {
        (connection["source"], connection["target"]): connection.get("synapse")
        for connection in _read(configs, "jiang24_stp", "connectivity.yaml")["connections"]
    }

    assert len(synapses) == len(data.stp)
    for entry in synapses.values():
        assert entry["model"] == "tsodyks_synapse"
    assert synapses["stp_E_to_PV"]["parameters"]["tau_psc"] == data.tau_syn_ex
    assert synapses["stp_SOM_to_E"]["parameters"]["tau_psc"] == data.tau_syn_in

    # A population's own parameters (E to E, per pair of layers), else its cell type's.
    assert by_pair["L23_E", "L4_E"] == "stp_L23_E_to_L4_E"
    assert by_pair["L5_E", "L6_PV"] == "stp_E_to_PV"
    assert by_pair["L6_SOM", "L4_PV"] == "stp_SOM_to_PV"
    # Static: onto and from VIP, SOM to SOM.
    for pair in (("L23_E", "L23_VIP"), ("L23_VIP", "L23_SOM"), ("L5_SOM", "L5_SOM")):
        assert by_pair[pair] is None
    # The E to E pairs of layers without parameters are not connected at all.
    for pair in (("L23_E", "L6_E"), ("L6_E", "L23_E"), ("L6_E", "L4_E")):
        assert stp_key(*pair) is None
        assert pair not in by_pair
