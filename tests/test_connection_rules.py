"""Connection rules, synapse models and receptor ports."""

import logging

import nest
import numpy as np
import pytest

from microcircuit_lab.backends.nest.simulator import NestBackend
from microcircuit_lab.config.background_inputs import BackgroundInputConfig
from microcircuit_lab.config.connection_table import ConnectionTable
from microcircuit_lab.config.connectivity import (
    ConnectionConfig,
    DelayDistribution,
    WeightDistribution,
)
from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.config.neurons import NeuronConfig, NeuronParams
from microcircuit_lab.config.populations import PopulationConfig
from microcircuit_lab.config.reference import ReferenceConfig
from microcircuit_lab.config.scaling import ScalingConfig
from microcircuit_lab.config.simulation import SimulationConfig
from microcircuit_lab.config.synapses import SynapseEntry
from microcircuit_lab.network.mean_input import expected_synapses, full_num_synapses
from microcircuit_lab.network.prepare import prepare_network

SIZES = {"S": 100, "T": 50}


def _connection(rule="fixed_total_number", weight=10.0, unit="PSC", source="S", target="T", **fields):
    return ConnectionConfig(
        source=source,
        target=target,
        rule=rule,
        weight=WeightDistribution(mean=weight, rel_std=0.0, distribution="fixed", unit=unit),
        delay=DelayDistribution(mean=1.0, rel_std=0.0, distribution="fixed"),
        **fields,
    )


def _network(connections, synapses=None, scaling=None, background_synapse=None, target_neuron=None):
    neuron = NeuronConfig(
        name="plain",
        model="iaf_psc_exp",
        parameters=NeuronParams(C_m=250.0, tau_m=10.0, tau_syn_ex=0.5, tau_syn_in=0.5),
    )
    populations = {
        name: PopulationConfig(
            name=name,
            size=size,
            neuron=target_neuron if (name == "T" and target_neuron) else neuron,
            background_indegree=100,
        )
        for name, size in SIZES.items()
    }
    background = {
        name: BackgroundInputConfig(
            rate=8.0,
            weight=WeightDistribution(mean=10.0, rel_std=0.0, distribution="fixed", unit="PSC"),
            delay=DelayDistribution(mean=1.0, rel_std=0.0, distribution="fixed"),
            synapse=background_synapse if name == "T" else None,
        )
        for name in SIZES
    }
    return NetworkConfig(
        populations=populations,
        connections=connections,
        background_inputs=background,
        scaling=scaling or ScalingConfig(),
        reference=ReferenceConfig(full_mean_rates={"S": 5.0, "T": 5.0}),
        synapses=synapses or {},
    )


def _built_connections(network):
    backend = NestBackend(network, SimulationConfig(print_time=False))
    backend.build()
    connections = nest.GetConnections(backend.get_population("S"), backend.get_population("T"))
    return backend, connections


@pytest.mark.parametrize(
    ("fields", "check"),
    [
        ({"n_synapses": 300}, lambda targets: len(targets) == 300),
        ({"rule": "fixed_indegree", "indegree": 7},
         lambda targets: set(np.unique(targets, return_counts=True)[1]) == {7}),
        ({"rule": "fixed_outdegree", "outdegree": 3}, lambda targets: len(targets) == 300),
        ({"rule": "pairwise_bernoulli", "p": 0.2}, lambda targets: 800 < len(targets) < 1200),
    ],
)
def test_each_rule_places_its_synapses(fields, check):
    _, connections = _built_connections(_network([_connection(**fields)]))
    assert check(np.array(connections.get("target")))
    nest.ResetKernel()


def test_a_rule_takes_its_own_number_only():
    with pytest.raises(ValueError, match="takes the number 'p'"):
        _connection(rule="pairwise_bernoulli", n_synapses=10)
    with pytest.raises(ValueError, match=r"remove \['n_synapses'\]"):
        _connection(rule="fixed_indegree", indegree=5, n_synapses=10)
    with pytest.raises(ValueError, match="'one_to_one' takes no number"):
        _connection(rule="one_to_one", n_synapses=10)
    with pytest.raises(ValueError, match="'my_rule' takes no number"):
        _connection(rule="my_rule", p=0.1)
    with pytest.raises(ValueError, match="takes no parameters"):
        _connection(rule="all_to_all", parameters={"width": 1})


def test_one_to_one_and_all_to_all_in_nest():
    network = _network([_connection(rule="one_to_one", source="S", target="S"), _connection(rule="all_to_all")])
    backend = NestBackend(network, SimulationConfig(print_time=False))
    backend.build()
    S, T = backend.get_population("S"), backend.get_population("T")

    one = nest.GetConnections(S, S)
    assert np.array_equal(one.get("source"), one.get("target")) and len(one) == SIZES["S"]
    assert len(nest.GetConnections(S, T)) == SIZES["S"] * SIZES["T"]
    nest.ResetKernel()


def test_one_to_one_needs_populations_of_the_same_size():
    with pytest.raises(ValueError, match="one_to_one needs populations of the same size"):
        _network([_connection(rule="one_to_one")])


def test_nest_runs_its_own_rule_with_its_parameters():
    network = _network([_connection(rule="pairwise_poisson", parameters={"pairwise_avg_num_conns": 2.0})])
    _, connections = _built_connections(network)
    expected = 2.0 * SIZES["S"] * SIZES["T"]
    assert abs(len(connections) - expected) < 5 * np.sqrt(expected)
    nest.ResetKernel()


@pytest.mark.parametrize(
    ("connection", "scaling", "message"),
    [
        (dict(rule="one_to_one", source="S", target="S"), dict(N_scaling=0.5, K_scaling=0.5), "K_scaling must be 1"),
        (dict(rule="all_to_all"), dict(N_scaling=0.5, K_scaling=1.0), "K_scaling must equal N_scaling"),
        (dict(rule="ring", parameters={"width": 2}), dict(N_scaling=0.5), "rule 'ring' is not a shared one and cannot be scaled"),
    ],
)
def test_rules_that_cannot_follow_the_scaling_are_an_error(connection, scaling, message):
    network = _network([_connection(**connection)], scaling=ScalingConfig(preserve_mean_input=False, **scaling))
    with pytest.raises(ValueError, match=message):
        prepare_network(network)


def test_the_new_rules_scale_where_they_can():
    scaling = ScalingConfig(N_scaling=0.5, K_scaling=0.5, preserve_mean_input=False)
    network = prepare_network(_network([_connection(rule="all_to_all")], scaling=scaling))
    assert network.connections["rule"][0] == "all_to_all"
    scaling = ScalingConfig(N_scaling=0.5, preserve_mean_input=False)
    connection = _connection(rule="one_to_one", source="S", target="S")
    assert len(prepare_network(_network([connection], scaling=scaling)).connections) == 1


def test_project_distributions_are_for_connections_only_and_scale_their_delays_only():
    with pytest.raises(ValueError, match="takes no parameters"):
        WeightDistribution(mean=1.0, rel_std=0.0, unit="PSC", distribution="normal", parameters={"a": 1})

    def connection(weight="fixed", delay="fixed"):
        params = {"weight": {"a": 1} if weight != "fixed" else None, "delay": {"a": 1} if delay != "fixed" else None}
        return _connection(n_synapses=100).model_copy(update={
            "weight": WeightDistribution(mean=10.0, rel_std=0.0, unit="PSC", distribution=weight, parameters=params["weight"]),
            "delay": DelayDistribution(mean=1.0, rel_std=0.0, distribution=delay, parameters=params["delay"]),
        })

    scaling = ScalingConfig(N_scaling=0.5, K_scaling=0.5, preserve_mean_input=False)
    with pytest.raises(ValueError, match="weights from a project distribution cannot be scaled"):
        prepare_network(_network([connection(weight="mine")], scaling=scaling))
    prepare_network(_network([connection(delay="mine")], scaling=scaling))

    network = _network([connection()])
    background = network.background_inputs["S"].model_copy(
        update={"weight": WeightDistribution(mean=10.0, rel_std=0.0, unit="PSC", distribution="mine", parameters={"a": 1})}
    )
    with pytest.raises(ValueError, match="background input of S has a weight from project distribution 'mine'"):
        NetworkConfig.model_validate({**network.model_dump(), "background_inputs": {**network.background_inputs, "S": background}})


def test_csv_keeps_project_rules_and_their_parameters(tmp_path):
    rows = [
        _connection(n_synapses=300),
        _connection(rule="one_to_one", source="S", target="S"),
        _connection(rule="ring", source="T", target="T", parameters={"width": 2, "p0": 0.5}),
        _connection(source="T", target="S", n_synapses=10).model_copy(update={
            "weight": WeightDistribution(mean=1.0, rel_std=0.0, unit="PSC", distribution="mine", parameters={"a": 1.5}),
        }),
    ]
    table = ConnectionTable.from_yaml_rows(rows)
    table.write_csv(tmp_path / "connections.csv")

    assert ConnectionTable.read_csv(tmp_path / "connections.csv") == table
    assert table.to_yaml_rows()[2]["parameters"] == {"width": 2, "p0": 0.5}
    assert "n_synapses" not in table.to_yaml_rows()[1]


def test_scaling_keeps_each_rule_at_the_same_expected_synapses():
    scaling = ScalingConfig(N_scaling=0.5, K_scaling=0.5, preserve_mean_input=False)
    rules = [
        {"n_synapses": 1000},
        {"rule": "fixed_indegree", "indegree": 20},
        {"rule": "fixed_outdegree", "outdegree": 10},
        {"rule": "pairwise_bernoulli", "p": 0.2},
    ]
    for fields in rules:
        connection = _connection(**fields)
        full = expected_synapses(connection.rule, connection.number, *SIZES.values())
        scaled = prepare_network(_network([connection], scaling=scaling))
        sizes = [population.size for population in scaled.populations.values()]
        # both factors: half the neurons, each with half its synapses
        table = scaled.connections
        assert expected_synapses(table["rule"][0], table["number"][0], *sizes) == pytest.approx(full / 4)


def test_scaled_probability_above_one_is_an_error():
    scaling = ScalingConfig(N_scaling=0.1, K_scaling=1.0)
    with pytest.raises(ValueError, match="above 1"):
        prepare_network(_network([_connection(rule="pairwise_bernoulli", p=0.5)], scaling=scaling))


def test_a_pair_takes_one_entry_per_synapse_and_quantities_sum_them():
    synapses = {"depressing": SynapseEntry(model="tsodyks2_synapse", parameters={"U": 0.5})}
    with pytest.raises(ValueError, match="more than one entry"):
        _network([_connection(n_synapses=10), _connection(n_synapses=20)])
    with pytest.raises(ValueError, match="'missing', which is not defined"):
        _network([_connection(n_synapses=10, synapse="missing")])

    network = _network(
        [_connection(n_synapses=10), _connection(n_synapses=20, synapse="depressing")],
        synapses=synapses,
    )
    assert full_num_synapses(network)[1, 0] == 30
    _, connections = _built_connections(network)
    models = connections.get("synapse_model")
    assert models.count("static_synapse") == 10 and models.count("depressing") == 20
    assert set(nest.GetConnections(synapse_model="depressing").get("U")) == {0.5}
    nest.ResetKernel()


def test_receptor_ports(caplog):
    synapses = {
        "fast": SynapseEntry(model="static_synapse", receptor_port=1),
        "slow": SynapseEntry(model="static_synapse", receptor_port=2),
    }
    with pytest.raises(ValueError, match="unit: PSP weight on receptor port 1"):
        _network([_connection(n_synapses=10, synapse="fast", unit="PSP", weight=0.1)], synapses)

    # T has two receptor ports (1 and 2), each with its own time constant
    multisynapse = NeuronConfig(
        name="multi",
        model="iaf_psc_exp_multisynapse",
        parameters=NeuronParams(C_m=250.0, tau_m=10.0, tau_syn=[0.5, 5.0]),
    )
    network = _network(
        [_connection(n_synapses=10, synapse="fast"), _connection(n_synapses=20, synapse="slow")],
        synapses,
        background_synapse="fast",  # a multisynapse neuron has no port 0
        target_neuron=multisynapse,
    )

    _, connections = _built_connections(network)
    receptors = connections.get("receptor")
    assert receptors.count(1) == 10 and receptors.count(2) == 20
    nest.ResetKernel()

    # Scaled: the core can't compute the input on other ports, so it says so
    scaled = network.model_copy(update={"scaling": ScalingConfig(K_scaling=0.5)})
    with caplog.at_level(logging.WARNING):
        prepared = prepare_network(scaled)
    assert "not compensated for S -> T, S -> T" in caplog.text
    assert "background input lost by scaling is not compensated for T" in caplog.text
    # S's background input is on the default port, so S alone is compensated
    assert prepared.populations["S"].neuron.parameters.I_e > 0
    assert prepared.populations["T"].neuron.parameters.I_e is None  # nothing added, left unset


def test_receptor_port_by_name():
    # ht_neuron has named receptors and no I_e, which is left unset here.
    ht = NeuronConfig(name="ht", model="ht_neuron", parameters=NeuronParams())
    for port in ("NMDA", "AMPA"):
        synapses = {"named": SynapseEntry(model="static_synapse", receptor_port=port)}
        network = _network(
            [_connection(n_synapses=10, synapse="named")], synapses, background_synapse="named", target_neuron=ht
        )
        backend, connections = _built_connections(network)
        # GetConnections shows NEST's internal port, not the receptor_type given.
        assert len(connections) == 10
        assert backend.synapse_spec(1.0, 1.0, "named", "T")["receptor_type"] == (
            nest.GetDefaults("ht_neuron")["receptor_types"][port]
        )
        nest.ResetKernel()

    synapses = {"named": SynapseEntry(model="static_synapse", receptor_port="NMDAR")}
    network = _network([_connection(n_synapses=10, synapse="named")], synapses, target_neuron=ht)
    backend = NestBackend(network, SimulationConfig(print_time=False))
    with pytest.raises(ValueError, match="receptor_port 'NMDAR'.*'ht_neuron' of 'T' has the receptor types"):
        backend.synapse_spec(1.0, 1.0, "named", "T")
    # S is iaf_psc_exp, which has no receptor types
    with pytest.raises(ValueError, match="'iaf_psc_exp' of 'S' has no receptor types"):
        backend.synapse_spec(1.0, 1.0, "named", "S")
    # A number in quotes is not taken as a name.
    with pytest.raises(ValueError, match="without quotes: receptor_port: 1"):
        SynapseEntry(model="static_synapse", receptor_port="1")


def test_a_model_without_I_e_says_so_when_it_gets_one():
    ht = NeuronConfig(name="ht", model="ht_neuron", parameters=NeuronParams(I_e=5.0))
    synapses = {"named": SynapseEntry(model="static_synapse", receptor_port="AMPA")}
    network = _network([_connection(n_synapses=10, synapse="named")], synapses, background_synapse="named", target_neuron=ht)
    with pytest.raises(ValueError, match="'ht_neuron' has no I_e"):
        _built_connections(network)
    nest.ResetKernel()


def test_background_on_another_port():
    synapses = {"fast": SynapseEntry(model="static_synapse", receptor_port=1)}
    network = _network([_connection(n_synapses=10)], synapses, background_synapse="fast")
    dc = network.model_copy(update={"background_mode": "mean_current"})
    with pytest.raises(ValueError, match="background_mode: mean_current needs the mean background current"):
        prepare_network(dc)


def test_advanced_example_uses_every_feature():
    """The bundled example of these features loads, and still shows them all."""
    from microcircuit_lab.network.load import read_network

    network = read_network("configs/network/toy_two_areas_advanced")
    rules = set(network.connections["rule"])
    assert rules == {"pairwise_bernoulli", "fixed_indegree"}
    assert {entry.model for entry in network.synapses.values()} == {"static_synapse", "tsodyks2_synapse"}
    assert any(entry.receptor_port for entry in network.synapses.values())
    prepare_network(network)


def test_native_weights_are_not_compensated(caplog):
    """A native weight (e.g. nS) is not a current: compensating it would add a
    current computed from conductances."""
    native = _connection(n_synapses=1000, weight=1.0, unit="native")
    scaled = _network([native], scaling=ScalingConfig(K_scaling=0.5))
    background = {
        name: input_cfg.model_copy(
            update={"weight": input_cfg.weight.model_copy(update={"unit": "native"})}
        )
        for name, input_cfg in scaled.background_inputs.items()
    }
    scaled = scaled.model_copy(update={"background_inputs": background})

    with caplog.at_level(logging.WARNING):
        prepared = prepare_network(scaled)
    assert "not compensated for S -> T" in caplog.text
    assert all(p.neuron.parameters.I_e is None for p in prepared.populations.values())
    with pytest.raises(ValueError, match="native or uses another port"):
        prepare_network(scaled.model_copy(update={"background_mode": "mean_current"}))
