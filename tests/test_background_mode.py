"""Tests for background_mode ("poisson" vs "dc" background input).

"dc" reproduces Potjans & Diesmann (2014)'s comparison of Poisson vs.
constant-current background drive (their Fig. 5): the background Poisson
generator is replaced network-wide by a constant current of equal mean.
"""

from pathlib import Path

import numpy as np
import pytest
import yaml

from microcircuit_lab.backends.nest import NestBackend
from microcircuit_lab.config.network import (
    BackgroundInputConfig,
    DelayDistribution,
    NetworkConfig,
    NeuronConfig,
    NeuronParams,
    PopulationConfig,
    ScalingConfig,
    WeightDistribution,
)
from microcircuit_lab.config.simulation import SimulationConfig
from microcircuit_lab.io.config import NetworkConfigLoader
from microcircuit_lab.io.files import read_network_directory
from microcircuit_lab.network import Network, NetworkPreprocessor
from microcircuit_lab.network.parameters import (
    background_indegrees,
    background_psc_weights,
    tau_syn_ex,
)
from microcircuit_lab.network.scaling import background_dc_current


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
        V0_mean=-65.0,
        V0_std=1.0,
        background_indegree=background_indegree,
    )


def _background(rate: float = 8.0, mean: float = 50.0) -> BackgroundInputConfig:
    return BackgroundInputConfig(
        rate=rate,
        weight=WeightDistribution(mean=mean, rel_std=0.0, distribution="fixed", unit="PSC"),
        delay=DelayDistribution(mean=1.0, rel_std=0.0, distribution="fixed"),
    )


def _network(background_mode: str) -> NetworkConfig:
    return NetworkConfig(
        populations={"E": _population("E", _neuron())},
        connections=[],
        background_inputs={"E": _background()},
        background_mode=background_mode,
        scaling=ScalingConfig(),
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
        scaling=ScalingConfig(),
    )
    assert network.background_mode == "poisson"


def test_background_mode_rejects_unknown_value():
    with pytest.raises(Exception):
        _network("bogus")


# -----------------------------------------------------------------------------
# NetworkPreprocessor: "dc" replaces the Poisson rate with a constant current
# -----------------------------------------------------------------------------
def test_dc_mode_zeros_background_rate():
    network = NetworkPreprocessor(_network("dc")).process()

    assert network.background_inputs["E"].rate == 0.0


def test_poisson_mode_keeps_effective_background_rate():
    network = NetworkPreprocessor(_network("poisson")).process()

    # effective_rate = bg_rate * K_ext, per _apply_background_poisson_rates
    assert network.background_inputs["E"].rate == pytest.approx(8.0 * 100.0)


def test_dc_mode_adds_expected_current():
    network = NetworkPreprocessor(_network("dc")).process()

    expected = background_dc_current(
        PSC_ext=50.0,
        K_ext=100.0,
        bg_rate=8.0,
        tau_syn=0.5,
    )

    assert network.populations["E"].neuron.parameters.I_e == pytest.approx(expected)
    assert expected > 0.0


def test_poisson_mode_leaves_i_e_untouched():
    network = NetworkPreprocessor(_network("poisson")).process()

    assert network.populations["E"].neuron.parameters.I_e == 0.0


def test_dc_current_independent_of_k_scaling():
    """The DC replacement targets the full biological background input,
    so it must not depend on N/K scaling of the recurrent network."""

    scaled = _network("dc").model_copy(
        update={
            "scaling": ScalingConfig(N_scaling=0.5, K_scaling=0.5),
        }
    )
    unscaled = NetworkPreprocessor(_network("dc")).process()
    rescaled = NetworkPreprocessor(scaled).process()

    assert rescaled.populations["E"].neuron.parameters.I_e == pytest.approx(
        unscaled.populations["E"].neuron.parameters.I_e
    )


# -----------------------------------------------------------------------------
# NEST backend: no Poisson generator is created for "dc"
# -----------------------------------------------------------------------------
def test_dc_mode_creates_no_poisson_generator():
    network = NetworkPreprocessor(_network("dc")).process()
    simulation_config = SimulationConfig.model_validate({"t_sim": 5.0, "print_time": False})

    backend = NestBackend(network=Network(network), simulation_config=simulation_config)
    backend.build()

    assert backend.poisson_generators == {}


def test_poisson_mode_creates_poisson_generator():
    network = NetworkPreprocessor(_network("poisson")).process()
    simulation_config = SimulationConfig.model_validate({"t_sim": 5.0, "print_time": False})

    backend = NestBackend(network=Network(network), simulation_config=simulation_config)
    backend.build()

    assert "E" in backend.poisson_generators


def test_dc_mode_network_still_spikes():
    """Regression test: the constant current alone (no Poisson generator)
    should be enough to drive spiking, same as the Poisson-driven network."""

    # Strong enough background (K_ext=1000, weight=100) that the resulting
    # DC current (400 pA) clears this neuron's rheobase (~375 pA); the
    # small values used elsewhere in this file are for formula checks only
    # and are far too weak to make anything spike.
    strong_network = _network("dc").model_copy(
        update={
            "populations": {"E": _population("E", _neuron(), background_indegree=1000.0)},
            "background_inputs": {"E": _background(rate=8.0, mean=100.0)},
        }
    )
    network = NetworkPreprocessor(strong_network).process()
    simulation_config = SimulationConfig.model_validate({"t_sim": 500.0, "print_time": False})

    backend = NestBackend(network=Network(network), simulation_config=simulation_config)
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
    data["background_mode"] = "dc"
    background_path.write_text(yaml.safe_dump(data))

    network_files = read_network_directory(network_dir)
    network = NetworkConfigLoader(network_files).build()

    assert network.background_mode == "dc"


def test_dc_matches_poisson_mean_input():
    """The DC-replaced background current should equal the mean input the
    Poisson-driven background would deliver on average, since both start
    from the same rate/weight/indegree."""

    bio = _network("poisson")
    dc = NetworkPreprocessor(_network("dc")).process()

    expected = background_dc_current(
        PSC_ext=background_psc_weights(bio),
        K_ext=background_indegrees(bio),
        bg_rate=np.asarray(
            [bio.background_inputs[name].rate for name in bio.populations]
        ),
        tau_syn=tau_syn_ex(bio),
    )

    for i, name in enumerate(bio.populations):
        assert dc.populations[name].neuron.parameters.I_e == pytest.approx(expected[i])
        assert dc.background_inputs[name].rate == 0.0
