"""Neuron parameters and initial states drawn separately for every neuron."""

import nest
import numpy as np
import pytest

from microcircuit_lab.backends.nest.simulator import NestBackend
from microcircuit_lab.config.connectivity import (
    ConnectionConfig,
    DelayDistribution,
    WeightDistribution,
)
from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.config.neurons import NeuronConfig, NeuronParams
from microcircuit_lab.config.populations import PopulationConfig
from microcircuit_lab.config.simulation import SimulationConfig


def _network(C_m) -> NetworkConfig:
    neuron = NeuronConfig(
        name="n",
        model="iaf_psc_exp",
        parameters=NeuronParams(
            C_m=C_m,
            tau_m=10.0,
            tau_syn_ex=0.5,
            tau_syn_in=0.5,
            V_th={"distribution": "uniform", "min": -52.0, "max": -48.0},
            t_ref={"distribution": "exponential", "beta": 3.0},
        ),
    )
    population = PopulationConfig(
        name="E",
        size=200,
        neuron=neuron,
        initial_state={"V_m": {"distribution": "normal", "mean": -60.0, "std": 2.0}},
    )
    connection = ConnectionConfig(
        source="E",
        target="E",
        n_synapses=10,
        weight=WeightDistribution(mean=0.1, rel_std=0.0, distribution="fixed", unit="pA"),
        delay=DelayDistribution(mean=1.0, rel_std=0.0, distribution="fixed"),
    )
    return NetworkConfig(
        populations={"E": population},
        connections=[connection],
        poisson_background={},
    )


def test_drawn_values_differ_per_neuron_and_numbers_do_not() -> None:
    backend = NestBackend(_network(C_m=250.0), SimulationConfig(print_time=False))
    backend.build()
    nodes = backend.get_population("E")

    V_th = np.array(nodes.get("V_th"))
    V_m = np.array(nodes.get("V_m"))
    assert V_th.min() >= -52.0 and V_th.max() <= -48.0 and V_th.std() > 0.5
    assert abs(V_m.mean() + 60.0) < 0.5 and 1.5 < V_m.std() < 2.5
    assert set(nodes.get("C_m")) == {250.0}
    t_ref = np.array(nodes.get("t_ref"))
    assert t_ref.min() >= 0.0 and 2.0 < t_ref.mean() < 4.0
    nest.ResetKernel()


def test_unknown_distribution_names_the_available_ones() -> None:
    network = _network(C_m={"distribution": "gaussian", "mean": 250.0, "std": 10.0})
    with pytest.raises(ValueError, match=r"no distribution 'gaussian'.*'normal'"):
        NestBackend(network, SimulationConfig(print_time=False)).build()


def test_distribution_without_all_its_arguments_is_rejected() -> None:
    network = _network(C_m={"distribution": "normal", "mean": 250.0})
    with pytest.raises(ValueError, match=r"'normal' needs \['std'\]"):
        NestBackend(network, SimulationConfig(print_time=False)).build()
