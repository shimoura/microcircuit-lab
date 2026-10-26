"""Tests for background_mode ("poisson" vs "mean_current" background input).

"mean_current" reproduces Potjans & Diesmann (2014)'s comparison of Poisson vs.
constant-current background drive (their Fig. 5): the background Poisson
generator is replaced network-wide by a constant current of equal mean.
"""

from pathlib import Path

import pytest
import yaml

from microcircuit_lab.backends.nest.simulator import NestBackend
from microcircuit_lab.builder_tools import scale_network
from microcircuit_lab.config.background_inputs import BackgroundInputConfig
from microcircuit_lab.config.connectivity import DelayDistribution, WeightDistribution
from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.config.neurons import NeuronConfig, NeuronParams
from microcircuit_lab.config.populations import PopulationConfig
from microcircuit_lab.config.simulation import SimulationConfig
from microcircuit_lab.network.compensation import mean_current
from microcircuit_lab.network.load import assemble_network, read_network_files
from microcircuit_lab.network.mean_input import (
    background_indegrees,
    background_rates,
    background_weights,
    tau_syn_ex,
)
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


def _population(name: str, neuron: NeuronConfig, background_indegree: float = 100.0) -> PopulationConfig:
    return PopulationConfig(
        name=name,
        size=10,
        neuron=neuron,
        initial_state={"V_m": {"distribution": "normal", "mean": -65.0, "std": 1.0}},
        background_indegree=background_indegree,
    )


def _background(rate: float = 8.0, mean: float = 50.0) -> BackgroundInputConfig:
    return BackgroundInputConfig(
        rate=rate,
        weight=WeightDistribution(mean=mean, rel_std=0.0, distribution="fixed", unit="pA"),
        delay=DelayDistribution(mean=1.0, rel_std=0.0, distribution="fixed"),
    )


def _network(background_mode: str) -> NetworkConfig:
    return NetworkConfig(
        populations={"E": _population("E", _neuron())},
        connections=[],
        background_inputs={"E": _background()},
        background_mode=background_mode,
    )


# -----------------------------------------------------------------------------
# NetworkConfig defaults and validation
# -----------------------------------------------------------------------------
def test_background_mode_defaults_to_poisson():
    population = _population("E", _neuron())
    network = NetworkConfig(
        populations={"E": population},
        connections=[],
        background_inputs={"E": _background()},
    )
    assert network.background_mode == "poisson"


# -----------------------------------------------------------------------------
# prepare_network: "mean_current" replaces the Poisson rate with a constant current
# -----------------------------------------------------------------------------
def test_dc_mode_zeros_background_rate():
    network = prepare_network(_network("mean_current"))

    assert network.background_inputs["E"].rate == 0.0


def test_poisson_mode_keeps_effective_background_rate():
    network = prepare_network(_network("poisson"))

    # effective_rate = bg_rate * K_ext, per _apply_background_poisson_rates
    assert network.background_inputs["E"].rate == pytest.approx(8.0 * 100.0)


def test_poisson_mode_leaves_i_e_untouched():
    network = prepare_network(_network("poisson"))

    assert network.populations["E"].neuron.parameters.I_e == 0.0


def test_dc_current_independent_of_k_scaling():
    """The DC replacement targets the full biological background input: in a
    scaled network, the current from its scaled background plus the
    compensation of the background lost by scaling."""

    scaled = scale_network(
        _network("mean_current"), N_scaling=0.5, K_scaling=0.5, scaled_from="test",
        compensate_recurrent_input=False,
    )
    unscaled = prepare_network(_network("mean_current"))
    rescaled = prepare_network(scaled)

    assert rescaled.populations["E"].neuron.parameters.I_e == pytest.approx(
        unscaled.populations["E"].neuron.parameters.I_e
    )


# -----------------------------------------------------------------------------
# NEST backend: no Poisson generator is created for "mean_current"
# -----------------------------------------------------------------------------
def test_dc_mode_creates_no_poisson_generator():
    network = prepare_network(_network("mean_current"))
    simulation_config = SimulationConfig.model_validate({"t_sim": 5.0, "print_time": False})

    backend = NestBackend(network=network, simulation_config=simulation_config)
    backend.build()

    assert backend.background_generators == {}


def test_poisson_mode_creates_poisson_generator():
    network = prepare_network(_network("poisson"))
    simulation_config = SimulationConfig.model_validate({"t_sim": 5.0, "print_time": False})

    backend = NestBackend(network=network, simulation_config=simulation_config)
    backend.build()

    assert "E" in backend.background_generators


def test_dc_mode_network_still_spikes():
    """Regression test: the constant current alone (no Poisson generator)
    should be enough to drive spiking, same as the Poisson-driven network."""

    # Strong enough background (K_ext=1000, weight=100) that the resulting
    # DC current (400 pA) clears this neuron's rheobase (~375 pA); the
    # small values used elsewhere in this file are for formula checks only
    # and are far too weak to make anything spike.
    strong_network = _network("mean_current").model_copy(
        update={
            "populations": {"E": _population("E", _neuron(), background_indegree=1000.0)},
            "background_inputs": {"E": _background(rate=8.0, mean=100.0)},
        }
    )
    network = prepare_network(strong_network)
    simulation_config = SimulationConfig.model_validate({"t_sim": 500.0, "print_time": False})

    backend = NestBackend(network=network, simulation_config=simulation_config)
    backend.build()
    backend.simulate()

    events = backend.get_spike_events("E")
    assert len(events["times"]) > 0


# -----------------------------------------------------------------------------
# YAML loading: background_mode is read from background_inputs.yaml
# -----------------------------------------------------------------------------
def test_loader_reads_background_mode_from_yaml(tmp_path: Path) -> None:
    import shutil

    network_dir = tmp_path / "network"
    shutil.copytree("configs/network/toy", network_dir)

    background_path = network_dir / "background_inputs.yaml"
    data = yaml.safe_load(background_path.read_text())
    data["background_mode"] = "mean_current"
    background_path.write_text(yaml.safe_dump(data))

    network_files = read_network_files(network_dir)
    network = assemble_network(network_files)

    assert network.background_mode == "mean_current"


def test_dc_matches_poisson_mean_input():
    """The DC-replaced background current should equal the mean input the
    Poisson-driven background would deliver on average, since both start
    from the same rate/weight/indegree."""

    bio = _network("poisson")
    dc = prepare_network(_network("mean_current"))

    expected = mean_current(
        weight=background_weights(bio),
        indegree=background_indegrees(bio),
        rate=background_rates(bio),
        tau_syn=tau_syn_ex(bio),
    )

    for i, name in enumerate(bio.populations):
        assert dc.populations[name].neuron.parameters.I_e == pytest.approx(expected[i])
        assert dc.background_inputs[name].rate == 0.0


# -----------------------------------------------------------------------------
# generator: populations with the same name share one Poisson generator
# -----------------------------------------------------------------------------
def _two_populations(generators=("A", "A"), rates=(8.0, 8.0), background_mode="poisson") -> NetworkConfig:
    neuron = _neuron()
    return NetworkConfig(
        populations={name: _population(name, neuron) for name in ("E1", "E2")},
        connections=[],
        background_inputs={
            name: _background(rate=rate).model_copy(update={"generator": generator})
            for name, generator, rate in zip(("E1", "E2"), generators, rates)
        },
        background_mode=background_mode,
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


def test_a_generator_name_with_mean_current_is_an_error():
    with pytest.raises(ValueError, match="background_mode is mean_current"):
        _two_populations(background_mode="mean_current")
