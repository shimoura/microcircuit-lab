"""Tests for replace_background_by_mean_current (and the shared generators).

The step reproduces Potjans & Diesmann (2014)'s comparison of Poisson vs.
constant-current background drive (their Fig. 5): the background Poisson
input is replaced by a constant current of equal mean, and the network
that is written shows no Poisson input at all.
"""

from pathlib import Path

import pytest
import yaml

from microcircuit_lab.backends.nest.simulator import NestBackend
from microcircuit_lab.builder_tools import (
    replace_background_by_mean_current,
    scale_network,
    write_network,
)
from microcircuit_lab.builder_tools.constant_current import mean_current
from microcircuit_lab.builder_tools.mean_input import (
    background_indegrees,
    background_rates,
    background_weights,
    tau_syn_ex,
)
from microcircuit_lab.config.connectivity import DelayDistribution, WeightDistribution
from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.config.neurons import NeuronConfig, NeuronParams
from microcircuit_lab.config.poisson_background import PoissonBackgroundConfig
from microcircuit_lab.config.populations import PopulationConfig
from microcircuit_lab.config.simulation import SimulationConfig
from microcircuit_lab.network.load import read_network, read_network_files
from microcircuit_lab.network.prepare import prepare_network


def _neuron(**overrides) -> NeuronConfig:
    params = dict(
        C_m=250.0,
        tau_m=10.0,
        tau_syn_ex=0.5,
        tau_syn_in=0.5,
        E_L=-65.0,
        V_reset=-65.0,
        V_th=-50.0,
        t_ref=2.0,
        I_e=0.0,
    )
    params.update(overrides)
    return NeuronConfig(name="exc", model="iaf_psc_exp", parameters=NeuronParams(**params))


def _population(name: str, neuron: NeuronConfig) -> PopulationConfig:
    return PopulationConfig(
        name=name,
        size=10,
        neuron=neuron,
        initial_state={"V_m": {"distribution": "normal", "mean": -65.0, "std": 1.0}},
    )


def _background(rate: float = 8.0, mean: float = 50.0, indegree: float = 100.0) -> PoissonBackgroundConfig:
    return PoissonBackgroundConfig(
        rate=rate,
        indegree=indegree,
        weight=WeightDistribution(mean=mean, rel_std=0.0, distribution="fixed", unit="pA"),
        delay=DelayDistribution(mean=1.0, rel_std=0.0, distribution="fixed"),
    )


def _network() -> NetworkConfig:
    return NetworkConfig(
        populations={"E": _population("E", _neuron())},
        connections=[],
        poisson_background={"E": _background()},
    )


# -----------------------------------------------------------------------------
# replace_background_by_mean_current
# -----------------------------------------------------------------------------
def test_the_background_becomes_the_mean_current_and_is_gone():
    poisson = _network()
    replaced = replace_background_by_mean_current(poisson)

    expected = mean_current(
        weight=background_weights(poisson),
        indegree=background_indegrees(poisson),
        rate=background_rates(poisson),
        tau_syn=tau_syn_ex(poisson),
    )
    assert replaced.populations["E"].neuron.parameters.I_e == pytest.approx(expected[0])
    assert replaced.poisson_background == {}
    # the network it was given is not changed
    assert poisson.poisson_background["E"].indegree == 100.0


def test_the_current_is_the_full_scale_one_after_scaling():
    """The replaced background of a scaled network is its scaled background
    plus the compensation of the background lost by scaling: the full-scale mean."""

    scaled = scale_network(
        _network(), N_scaling=0.5, K_scaling=0.5, scaled_from="test",
        compensate_recurrent_input=False,
    )

    assert replace_background_by_mean_current(scaled).populations["E"].neuron.parameters.I_e == pytest.approx(
        replace_background_by_mean_current(_network()).populations["E"].neuron.parameters.I_e
    )


def test_a_network_without_background_is_written_and_read_back(tmp_path: Path) -> None:
    replaced = write_network(replace_background_by_mean_current(_network()), tmp_path / "net")

    assert read_network(tmp_path / "net") == replaced


def test_an_old_file_with_background_mode_fails_with_the_new_way(tmp_path: Path) -> None:
    import shutil

    shutil.copytree("configs/network/toy", tmp_path / "network")
    path = tmp_path / "network" / "poisson_background.yaml"
    data = yaml.safe_load(path.read_text())
    data["background_mode"] = "mean_current"
    path.write_text(yaml.safe_dump(data))

    with pytest.raises(ValueError, match="replace_background_by_mean_current"):
        read_network_files(tmp_path / "network")


def test_old_names_fail_with_the_new_form(tmp_path: Path) -> None:
    import shutil

    shutil.copytree("configs/network/toy", tmp_path / "network")
    folder = tmp_path / "network"
    entry = yaml.safe_load((folder / "poisson_background.yaml").read_text())["poisson_background"]["E"]

    (folder / "poisson_background.yaml").write_text(yaml.safe_dump({"background_inputs": {"E": entry}}))
    with pytest.raises(ValueError, match="now poisson_background"):
        read_network_files(folder)

    shutil.copy("configs/network/toy/poisson_background.yaml", folder / "poisson_background.yaml")
    manifest = (folder / "network.yaml").read_text()
    (folder / "network.yaml").write_text(manifest.replace("poisson_background:", "background_inputs:"))
    with pytest.raises(ValueError, match="write `poisson_background: poisson_background.yaml`"):
        read_network_files(folder)

    (folder / "network.yaml").write_text(manifest)
    populations = yaml.safe_load((folder / "populations.yaml").read_text())
    populations["populations"][0]["background_indegree"] = 1000
    (folder / "populations.yaml").write_text(yaml.safe_dump(populations))
    with pytest.raises(ValueError, match="as `indegree`"):
        read_network_files(folder)


# -----------------------------------------------------------------------------
# NEST backend: Poisson generators for the background, none once it is replaced
# -----------------------------------------------------------------------------
def test_poisson_background_creates_a_generator_and_the_replaced_one_does_not():
    simulation_config = SimulationConfig.model_validate({"t_sim": 5.0, "print_time": False})

    poisson = NestBackend(network=prepare_network(_network()), simulation_config=simulation_config)
    poisson.build()
    replaced = NestBackend(
        network=prepare_network(replace_background_by_mean_current(_network())),
        simulation_config=simulation_config,
    )
    replaced.build()

    assert "E" in poisson.background_generators
    assert replaced.background_generators == {}


def test_the_mean_current_alone_drives_spiking():
    # Strong enough background (K_ext=1000, weight=100) that the current
    # (400 pA) clears this neuron's rheobase (~375 pA); the small values
    # used elsewhere in this file are for formula checks only.
    strong_network = _network().model_copy(
        update={
            "poisson_background": {"E": _background(rate=8.0, mean=100.0, indegree=1000.0)},
        }
    )
    network = prepare_network(replace_background_by_mean_current(strong_network))
    simulation_config = SimulationConfig.model_validate({"t_sim": 500.0, "print_time": False})

    backend = NestBackend(network=network, simulation_config=simulation_config)
    backend.build()
    backend.simulate()

    assert len(backend.get_spike_events("E")["times"]) > 0


# -----------------------------------------------------------------------------
# generator: populations with the same name share one Poisson generator
# -----------------------------------------------------------------------------
def _two_populations(generators=("A", "A"), rates=(8.0, 8.0)) -> NetworkConfig:
    neuron = _neuron()
    return NetworkConfig(
        populations={name: _population(name, neuron) for name in ("E1", "E2")},
        connections=[],
        poisson_background={
            name: _background(rate=rate).model_copy(update={"generator": generator})
            for name, generator, rate in zip(("E1", "E2"), generators, rates)
        },
    )


def test_populations_with_the_same_generator_name_share_one_generator():
    simulation_config = SimulationConfig.model_validate({"t_sim": 5.0, "print_time": False})

    shared = NestBackend(network=prepare_network(_two_populations()), simulation_config=simulation_config)
    shared.build()
    own = NestBackend(
        network=prepare_network(_two_populations(generators=(None, None))),
        simulation_config=simulation_config,
    )
    own.build()

    assert shared.background_generators["E1"] == shared.background_generators["E2"]
    assert own.background_generators["E1"] != own.background_generators["E2"]


def test_a_shared_generator_needs_the_same_input_for_its_populations():
    with pytest.raises(ValueError, match="generator 'A' need the same rate"):
        _two_populations(rates=(8.0, 9.0))
