"""Neuron parameters and initial states drawn separately for every neuron."""

import nest
import numpy as np
import pytest

from microcircuit_lab.backends.nest.simulator import NestBackend
from microcircuit_lab.config.connectivity import ConnectionConfig
from microcircuit_lab.config.distributions import DelayDistribution, WeightDistribution
from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.config.neurons import NeuronConfig, NeuronParams
from microcircuit_lab.config.populations import PopulationConfig
from microcircuit_lab.config.simulation import SimulationConfig


def erlang2(beta):
    # A distribution of the project (extensions/nest/), found in this module.
    return nest.random.exponential(beta=beta) + nest.random.exponential(beta=beta)


def _network(C_m, V_m=None, weight=None) -> NetworkConfig:
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
        initial_state={"V_m": V_m or {"distribution": "normal", "mean": -60.0, "std": 2.0}},
    )
    connection = ConnectionConfig(
        source="E",
        target="E",
        n_synapses=1000,
        weight=weight or WeightDistribution(value=0.1, unit="pA"),
        delay=DelayDistribution(value=1.0),
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


@pytest.mark.parametrize("backend", ["nest", "brian2"])
def test_both_simulators_draw_with_the_same_names_and_bounds(backend) -> None:
    # exponential is NEST's own, and an example of extensions/brian2/ for Brian2.
    V_m = {"distribution": "normal", "mean": -60.0, "std": 2.0, "upper_bound": -59.0, "bound_mode": "redraw"}
    network = _network(C_m=250.0, V_m=V_m)
    if backend == "nest":
        simulator = NestBackend(network, SimulationConfig(print_time=False))
    else:
        pytest.importorskip("brian2")
        from microcircuit_lab.backends.brian2.simulator import Brian2Backend

        simulator = Brian2Backend(network, SimulationConfig(print_time=False))
    simulator.build()
    nodes = simulator.get_population("E")
    if backend == "nest":
        V_m, V_th, t_ref = (np.array(nodes.get(name)) for name in ("V_m", "V_th", "t_ref"))
        nest.ResetKernel()
    else:
        import brian2 as b2

        neurons = simulator.populations["E"]
        V_m, V_th, t_ref = neurons.V_m[:] / b2.mV, neurons.V_th[:] / b2.mV, neurons.t_ref[:] / b2.ms

    assert V_m.max() <= -59.0 and V_m.std() > 0.3
    assert V_th.min() >= -52.0 and V_th.max() <= -48.0 and V_th.std() > 0.5
    assert t_ref.min() >= 0.0 and 2.0 < t_ref.mean() < 4.0


def test_a_project_distribution_draws_neuron_values_and_weights() -> None:
    weight = WeightDistribution(distribution="erlang2", beta=2.0, mean=4.0, unit="pA")
    network = _network(C_m={"distribution": "erlang2", "beta": 100.0}, weight=weight)
    backend = NestBackend(network, SimulationConfig(print_time=False), extensions=[__name__])
    backend.build()
    nodes = backend.get_population("E")
    C_m = np.array(nodes.get("C_m"))
    weights = np.array(nest.GetConnections(nodes, nodes).get("weight"))
    # erlang2 has mean 2 beta and standard deviation sqrt(2) beta.
    assert abs(C_m.mean() - 200.0) < 30.0 and abs(C_m.std() - 141.0) < 30.0
    assert abs(weights.mean() - 4.0) < 0.3
    nest.ResetKernel()


def test_unknown_distribution_names_the_available_ones() -> None:
    network = _network(C_m={"distribution": "gaussian", "mean": 250.0, "std": 10.0})
    with pytest.raises(ValueError, match=r"no distribution 'gaussian'.*'normal'"):
        NestBackend(network, SimulationConfig(print_time=False)).build()


def test_a_missing_or_unknown_argument_is_an_error() -> None:
    for C_m, problem in (({"distribution": "exponential"}, r"give \['beta'\]"),
                         ({"distribution": "exponential", "beta": 2.0, "bta": 1.0}, r"does not take \['bta'\]"),
                         ({"distribution": "exponential", "beta": 2.0, "std": 1.0}, r"does not take \['std'\]")):
        with pytest.raises(ValueError, match=rf"C_m of E \(neurons.yaml\): distribution 'exponential' .*{problem}"):
            NestBackend(_network(C_m=C_m), SimulationConfig(print_time=False)).build()
