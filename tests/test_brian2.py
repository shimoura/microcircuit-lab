"""Tests for the Brian2 simulator backend.

The networks use the models in ``extensions/brian2/``, found from the folder the
tests run from (the repository).
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from microcircuit_lab import Simulation
from microcircuit_lab.backends.brian2.models import (
    ConnectionRule,
    Distribution,
    NeuronModel,
    SynapseModel,
)
from microcircuit_lab.config.connectivity import (
    ConnectionConfig,
    DelayDistribution,
    WeightDistribution,
)
from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.config.neurons import NeuronConfig, NeuronParams
from microcircuit_lab.config.populations import PopulationConfig
from microcircuit_lab.config.reference import ReferenceConfig
from microcircuit_lab.config.simulation import RecordingConfig, SimulationConfig
from microcircuit_lab.config.stimuli import DcStimulusConfig
from microcircuit_lab.config.synapses import SynapseEntry

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("brian2") is None,
    reason="brian2 is not installed",
)

# Found by the test that passes this module in extensions.
pacemaker = NeuronModel(
    name="pacemaker",
    equations="dV_m/dt = (E_L - V_m)/tau_m : volt\nE_L : volt\ntau_m : second",
    threshold="V_m > -55*mV",
    reset="V_m = -70*mV",
    refractory="0*ms",
    excitatory="V_m",
    inhibitory="V_m",
    defaults={"E_L": -50.0, "tau_m": 10.0, "V_m": -70.0},
)


# Found by the tests of synapse models, with pacemaker above.
stdp = SynapseModel(
    name="stdp",
    model="""
    dapre/dt = -apre/tau_plus : 1 (event-driven)
    dapost/dt = -apost/tau_minus : 1 (event-driven)
    tau_plus : second (constant)
    tau_minus : second (constant)
    w_max : volt (constant)
    """,
    on_pre="""
    {target} += w_syn
    apre += 0.1
    w_syn = clip(w_syn*(1 + apost), 0*mV, w_max)
    """,
    on_post="""
    apost -= 0.1
    w_syn = clip(w_syn*(1 + apre), 0*mV, w_max)
    """,
    defaults={"tau_plus": 20.0, "tau_minus": 20.0, "w_max": 10.0},
)
two_pathways = SynapseModel(
    name="two_pathways",
    model="delay_slow : second (constant)",
    on_pre={"pre": "{target} += w_syn", "slow": "{target} += w_syn"},
    delays={"slow": "delay_slow"},
)
gap_neuron = NeuronModel(
    name="gap_neuron",
    equations="dV_m/dt = (E_L - V_m)/tau_m + I_gap/C_m : volt\nI_gap : amp\n"
    "E_L : volt\ntau_m : second\nC_m : farad",
    threshold="V_m > 0*mV",
    reset="V_m = -70*mV",
    refractory="0*ms",
    excitatory="V_m",
    inhibitory="V_m",
    defaults={"E_L": -70.0, "tau_m": 10.0, "C_m": 100.0, "V_m": -70.0, "I_gap": 0.0},
)
two_inputs = NeuronModel(
    name="two_inputs",
    equations="dV_m/dt = (E_L - V_m)/tau_m + (I_a + I_b)/C_m : volt\n"
    "dI_a/dt = -I_a/tau_m : amp\ndI_b/dt = -I_b/tau_m : amp\n"
    "E_L : volt\ntau_m : second\nC_m : farad",
    threshold="V_m > -55*mV",
    reset="V_m = -70*mV",
    refractory="0*ms",
    excitatory="I_a",
    inhibitory="I_a",
    defaults={"E_L": -50.0, "tau_m": 10.0, "C_m": 100.0, "V_m": -70.0},
)
gap = SynapseModel(
    name="gap",
    model="I_gap_post = g_gap*(V_m_pre - V_m_post) : amp (summed)\ng_gap : siemens (constant)",
    on_pre="",
    defaults={"g_gap": 10.0},
)


# Found by the tests of project rules and distributions, with pacemaker above.
ring = ConnectionRule(name="ring", condition="abs(index_pre - index_post) <= width")
by_target = Distribution(name="by_target", expression="mean * (1 + index_post) * step", redraw_rounds=0)
alternating = Distribution(name="alternating", expression="mean * (1 - 2*(index_post % 2))", redraw_rounds=0)
no_rounds = Distribution(name="no_rounds", expression="mean")
same_index_twice = ConnectionRule(name="same_index_twice", condition="index_pre == index_post", n="2")


# numpy compiles nothing: Cython would compile each test network first, which
# takes many minutes with an empty cache (as in CI).
NUMPY = {"codegen_target": "numpy"}


def _run(network_name: str, tmp_path: Path, t_sim: float = 200.0, backend_options=None) -> Simulation:
    simulation = Simulation.from_yaml(
        network_name=network_name, backend="brian2", backend_options={**NUMPY, **(backend_options or {})}
    )
    simulation.simulation_config = simulation.simulation_config.model_copy(
        update={
            "t_sim": t_sim,
            "print_time": False,
            "output": simulation.simulation_config.output.model_copy(
                update={"output_dir": tmp_path, "overwrite": True}
            ),
        }
    )
    simulation.run()
    return simulation


def _network(neuron_model: str, connections=(), stimuli=(), size: int = 50, synapses=None) -> NetworkConfig:
    neuron = NeuronConfig(name="plain", model=neuron_model, parameters=NeuronParams())
    populations = {
        "S": PopulationConfig(name="S", size=2 * size, neuron=neuron),
        "T": PopulationConfig(name="T", size=size, neuron=neuron),
    }
    return NetworkConfig(
        populations=populations,
        connections=list(connections),
        poisson_background={},
        stimuli=list(stimuli),
        synapses=synapses or {},
        reference=ReferenceConfig(full_mean_rates={"S": 5.0, "T": 5.0}),
    )


def _backend(network: NetworkConfig, **options):
    from microcircuit_lab.backends.brian2.simulator import Brian2Backend

    return Brian2Backend(network, SimulationConfig(t_sim=200.0, print_time=False), **NUMPY, **options)


def test_toy_runs_and_replots_without_brian2(tmp_path: Path) -> None:
    simulation = _run("toy", tmp_path)

    for pop_name in simulation.network.populations:
        assert len(simulation.backend.get_spike_events(pop_name)["times"]) > 0, pop_name

    # A saved run is re-plotted without Brian2: block its import.
    script = (
        "import sys; sys.modules['brian2'] = None\n"
        "from microcircuit_lab import Simulation\n"
        f"simulation = Simulation.from_run_dir({str(tmp_path)!r})\n"
        "print(sum(len(simulation.backend.get_spike_events(p)['times']) for p in simulation.network.populations))\n"
    )
    replotted = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True)
    n_spikes = sum(len(simulation.backend.get_spike_events(p)["times"]) for p in simulation.network.populations)
    assert int(replotted.stdout.split()[-1]) == n_spikes


def test_recorded_variables_are_saved_in_config_units(tmp_path: Path) -> None:
    from microcircuit_lab.backends import read_recording

    simulation = Simulation.from_yaml(network_name="toy", backend="brian2", backend_options=NUMPY)
    recording = {"V_m": {"sample_size": 3}, "I_syn_ex": {"sample_size": 3, "populations": ["I"]}}
    simulation.simulation_config = simulation.simulation_config.model_copy(
        update={
            "t_sim": 50.0,
            "print_time": False,
            "recording": RecordingConfig(variables=recording),
            "output": simulation.simulation_config.output.model_copy(
                update={"output_dir": tmp_path, "overwrite": True}
            ),
        }
    )
    simulation.run()

    senders, times, values = read_recording(tmp_path, "V_m")
    assert len(set(senders)) == 3 * len(simulation.network.populations)
    assert (np.diff(senders) >= 0).all()
    # Brian2 keeps volts: the file has mV.
    assert -100 < values.min() and values.max() < 0
    only = read_recording(tmp_path, "I_syn_ex")[0]
    assert set(only) == set(simulation.backend.get_population("I")[:3])


def _distinct_pairs(syn) -> bool:
    pairs = set(zip(syn.i[:].tolist(), syn.j[:].tolist()))
    return len(pairs) == len(syn) and all(i != j for i, j in pairs)


@pytest.mark.parametrize(
    ("rule", "number_kwargs", "check"),
    [
        ("fixed_total_number", {"n_synapses": 300}, lambda syn: len(syn) == 300),
        ("fixed_indegree", {"indegree": 7}, lambda syn: set(np.unique(syn.j[:], return_counts=True)[1]) == {7}),
        ("fixed_outdegree", {"outdegree": 3}, lambda syn: len(syn) == 300),
        ("pairwise_bernoulli", {"p": 0.2}, lambda syn: 800 < len(syn) < 1200),
        # Within one population, without autapses and multapses.
        (
            "fixed_indegree",
            {"indegree": 7, "source": "T", "allow_autapses": False, "allow_multapses": False},
            lambda syn: _distinct_pairs(syn) and set(np.unique(syn.j[:], return_counts=True)[1]) == {7},
        ),
        (
            "fixed_total_number",
            {"n_synapses": 2000, "source": "T", "allow_autapses": False, "allow_multapses": False},
            lambda syn: _distinct_pairs(syn) and len(syn) == 2000,
        ),
        ("one_to_one", {"source": "T"}, lambda syn: len(syn) == 50 and np.array_equal(syn.i[:], syn.j[:])),
        ("all_to_all", {}, lambda syn: len(syn) == 100 * 50 and _distinct_pairs(syn)),
    ],
)
def test_each_connection_rule(rule: str, number_kwargs: dict, check) -> None:
    number_kwargs = {"source": "S", **number_kwargs}
    connection = ConnectionConfig(
        target="T",
        rule=rule,
        weight=WeightDistribution(mean=10.0, rel_std=0.0, distribution="fixed", unit="pA"),
        delay=DelayDistribution(mean=1.0, rel_std=0.0, distribution="fixed"),
        **number_kwargs,
    )
    backend = _backend(_network("iaf_psc_exp", connections=[connection]))
    backend.build()
    assert len(backend.synapses) == 1
    assert check(backend.synapses[0])


def test_a_project_rule_connects_the_pairs_its_expressions_choose() -> None:
    connection = ConnectionConfig(
        source="T",
        target="T",
        rule="ring",
        parameters={"width": 1},
        allow_autapses=False,
        weight=WeightDistribution(mean=10.0, rel_std=0.0, distribution="fixed", unit="pA"),
        delay=DelayDistribution(mean=1.0, rel_std=0.0, distribution="fixed"),
    )
    backend = _backend(_network("iaf_psc_exp", connections=[connection]), extensions=[__name__])
    backend.build()

    # T is neurons 100-149 of the group (after S); each neuron to its neighbours.
    pairs = set(zip(backend.synapses[0].i[:].tolist(), backend.synapses[0].j[:].tolist()))
    assert pairs == {(a, b) for a in range(100, 150) for b in range(100, 150) if abs(a - b) == 1}


def _row(source, target, weight, delay, **fields):
    return ConnectionConfig(source=source, target=target, rule="all_to_all", weight=weight, delay=delay, **fields)


def test_project_distributions_next_to_shared_ones_in_one_synapses() -> None:
    fixed_delay = DelayDistribution(mean=1.0, rel_std=0.0, distribution="fixed")
    project = _row(
        "S", "T",
        WeightDistribution(mean=2.0, rel_std=0.0, unit="pA", distribution="by_target", parameters={"step": 0.5}),
        DelayDistribution(mean=1.0, rel_std=0.0, distribution="by_target", parameters={"step": 0.1}),
    )
    shared = _row("T", "T", WeightDistribution(mean=7.0, rel_std=0.0, distribution="fixed", unit="pA"), fixed_delay)
    backend = _backend(_network("iaf_psc_exp", connections=[project, shared]), extensions=[__name__])
    backend.build()

    import brian2 as b2

    (synapses,) = backend.synapses
    from_s = synapses.i[:] < 100
    index_post = synapses.j[:] - 100  # T is neurons 100-149 of the group
    assert np.allclose(synapses.w_syn[:][from_s] / b2.pA, 2.0 * (1 + index_post[from_s]) * 0.5)
    assert np.allclose(synapses.delay[:][from_s] / b2.ms, 1.0 * (1 + index_post[from_s]) * 0.1)
    assert np.allclose(synapses.w_syn[:][~from_s] / b2.pA, 7.0)
    assert np.allclose(synapses.delay[:][~from_s] / b2.ms, 1.0)


def test_a_project_weight_past_its_bound_is_clipped() -> None:
    weight = WeightDistribution(mean=3.0, rel_std=0.0, unit="pA", distribution="alternating")
    connection = _row("S", "T", weight, DelayDistribution(mean=1.0, rel_std=0.0, distribution="fixed"))
    backend = _backend(_network("iaf_psc_exp", connections=[connection]), extensions=[__name__])
    backend.build()

    import brian2 as b2

    w = backend.synapses[0].w_syn[:] / b2.pA
    odd = (backend.synapses[0].j[:] - 100) % 2 == 1
    assert np.all(w[odd] == 0.0) and np.allclose(w[~odd], 3.0)


def test_redraw_needs_the_distributions_redraw_rounds() -> None:
    weight = WeightDistribution(mean=3.0, rel_std=0.0, unit="pA", distribution="no_rounds")
    connection = _row("S", "T", weight, DelayDistribution(mean=1.0, rel_std=0.0, distribution="fixed"))
    network = _network("iaf_psc_exp", connections=[connection])
    with pytest.raises(ValueError, match="'no_rounds' has no redraw_rounds.*bound_mode: clip"):
        _backend(network, extensions=[__name__]).check()

    _backend(network.model_copy(update={"bound_mode": "clip"}), extensions=[__name__]).check()


def test_an_unknown_rule_says_where_to_define_it() -> None:
    connection = ConnectionConfig(
        source="S",
        target="T",
        rule="no_such_rule",
        weight=WeightDistribution(mean=10.0, rel_std=0.0, distribution="fixed", unit="pA"),
        delay=DelayDistribution(mean=1.0, rel_std=0.0, distribution="fixed"),
    )
    backend = _backend(_network("iaf_psc_exp", connections=[connection]))
    with pytest.raises(ValueError, match=r"no connection rule 'no_such_rule'.*ConnectionRule.*extensions/brian2/"):
        backend.check()


def test_redraw_keeps_the_sign_of_the_weights() -> None:
    connection = ConnectionConfig(
        source="S",
        target="T",
        rule="fixed_indegree",
        indegree=20,
        weight=WeightDistribution(mean=-10.0, rel_std=1.0, distribution="normal", unit="pA"),
        delay=DelayDistribution(mean=1.0, rel_std=0.0, distribution="fixed"),
    )
    backend = _backend(_network("iaf_psc_exp", connections=[connection]))
    backend.build()

    weights = np.asarray(backend.synapses[0].w_syn[:] / 1e-12)
    assert weights.max() < 0.0
    # Redrawn, not clipped: about 16 % of them would be 0 after clipping.
    assert abs(weights.mean() + 10.0 * 1.29) < 1.0


def test_lognormal_next_to_another_distribution_in_one_synapses() -> None:
    delay = DelayDistribution(mean=1.0, rel_std=0.0, distribution="fixed")
    lognormal = _row("S", "T", WeightDistribution(mean=50.0, rel_std=0.2, unit="pA", distribution="lognormal"), delay)
    normal = _row("T", "T", WeightDistribution(mean=20.0, rel_std=0.2, unit="pA", distribution="normal"), delay)
    backend = _backend(_network("iaf_psc_exp", connections=[lognormal, normal]))
    backend.build()

    import brian2 as b2

    (synapses,) = backend.synapses
    w = synapses.w_syn[:] / b2.pA
    from_s = synapses.i[:] < 100
    assert not np.isnan(w).any()
    assert abs(w[from_s].mean() - 50.0) < 2.0 and w[from_s].min() > 0.0
    assert abs(w[~from_s].mean() - 20.0) < 2.0 and w[~from_s].min() > 0.0


def test_a_project_rule_with_several_synapses_per_pair_needs_multapses() -> None:
    connection = ConnectionConfig(
        source="S",
        target="T",
        rule="same_index_twice",
        allow_multapses=False,
        weight=WeightDistribution(mean=1.0, rel_std=0.0, distribution="fixed", unit="pA"),
        delay=DelayDistribution(mean=1.0, rel_std=0.0, distribution="fixed"),
    )
    backend = _backend(_network("iaf_psc_exp", connections=[connection]), extensions=[__name__])
    with pytest.raises(ValueError, match="'same_index_twice' makes n = 2 synapses per pair"):
        backend.check()


def _synapse_network(neuron_model: str, synapse: str, parameters: dict, delay: float = 1.0, weight: float = 1.0):
    connection = _row(
        "S", "T",
        WeightDistribution(mean=weight, rel_std=0.0, unit="mV", distribution="fixed"),
        DelayDistribution(mean=delay, rel_std=0.0, distribution="fixed"),
        synapse=synapse,
    )
    entry = SynapseEntry(model=synapse, parameters=parameters)
    return _network(neuron_model, connections=[connection], size=5, synapses={synapse: entry})


def test_stdp_changes_the_weights_when_both_neurons_spike() -> None:
    backend = _backend(_synapse_network("pacemaker", "stdp", {}), extensions=[__name__])
    backend.build()
    import brian2 as b2

    before = backend.synapses[0].w_syn[:] / b2.mV
    backend.simulate()
    after = backend.synapses[0].w_syn[:] / b2.mV
    assert np.allclose(before, 1.0)
    assert not np.allclose(after, before)


def test_extra_pathway_has_its_own_delay() -> None:
    network = _synapse_network("pacemaker", "two_pathways", {"delay_slow": 7.0}, delay=2.0)
    backend = _backend(network, extensions=[__name__])
    backend.build()
    import brian2 as b2

    (synapses,) = backend.synapses
    assert np.allclose(synapses.slow.delay[:] / b2.ms, 7.0)
    assert np.allclose(synapses.delay[:] / b2.ms, 2.0)


def test_receptor_port_by_name_is_the_variable_added_to() -> None:
    def network(port):
        connection = _row(
            "S", "T",
            WeightDistribution(mean=5.0, rel_std=0.0, unit="pA", distribution="fixed"),
            DelayDistribution(mean=1.0, rel_std=0.0, distribution="fixed"),
            synapse="named",
        )
        entry = SynapseEntry(model="static_synapse", receptor_port=port)
        return _network("two_inputs", connections=[connection], size=5, synapses={"named": entry})

    backend = _backend(network("I_b"), extensions=[__name__])
    backend.build()
    backend.simulate()
    group = backend._group_of["T"].neurons
    assert np.all(group.I_a[:] == 0) and np.any(group.I_b[:] != 0)

    with pytest.raises(ValueError, match="'named' sets receptor_port 'I_c'.*no variable of that name"):
        _backend(network("I_c"), extensions=[__name__]).check()


def test_gap_junction_pulls_the_target_toward_the_source() -> None:
    backend = _backend(_synapse_network("gap_neuron", "gap", {}), extensions=[__name__])
    backend.build()
    import brian2 as b2

    neurons = backend._groups[0].neurons
    neurons.E_L[:10] = -50 * b2.mV  # S (10 neurons) holds near -50 mV; T would rest at -70 mV
    backend.simulate()
    assert np.mean(neurons.V_m[10:] / b2.mV) > -65.0
    assert np.all(neurons.I_gap[10:] > 0 * b2.amp)


def test_dc_stimulus_drives_spiking_only_during_pulse() -> None:
    stimulus = DcStimulusConfig(targets=["T"], amplitude=2000.0, start=50.0, stop=150.0)
    backend = _backend(_network("iaf_psc_exp", stimuli=[stimulus], size=5))
    backend.build()
    backend.simulate()

    times = backend.get_spike_events("T")["times"]
    assert len(times) > 0
    assert min(times) >= 50.0
    assert max(times) < 155.0


def test_model_from_a_model_module() -> None:
    backend = _backend(_network("pacemaker", size=5), extensions=[__name__])
    backend.build()
    backend.simulate()

    assert len(backend.get_spike_events("T")["times"]) > 0


def test_missing_model_fails_before_the_run_folder_and_says_where_to_define_it(tmp_path: Path) -> None:
    config = SimulationConfig(output={"output_dir": tmp_path / "runs"}, backend={"name": "brian2", "options": NUMPY})
    simulation = Simulation(network=_network("no_such_model"), simulation_config=config, network_name="n")
    with pytest.raises(ValueError, match=r"no neuron model 'no_such_model'.*extensions/brian2/.*--extensions"):
        simulation.run()

    assert not (tmp_path / "runs").exists()


@pytest.mark.parametrize("network_name", ["toy_stimulated", "toy_two_areas_advanced"])
def test_networks_with_every_feature_spike(network_name: str, tmp_path: Path) -> None:
    # Stimuli and a conductance-based model; drawn values, connection rules,
    # synapse models and receptor ports.
    simulation = _run(network_name, tmp_path, t_sim=100.0)

    for pop_name in simulation.network.populations:
        assert len(simulation.backend.get_spike_events(pop_name)["times"]) > 0, pop_name


def test_cpp_standalone_device(tmp_path: Path) -> None:
    simulation = _run("toy", tmp_path, t_sim=20.0, backend_options={"device": "cpp_standalone"})

    assert len(simulation.backend.get_spike_events("E")["times"]) > 0
    assert (tmp_path / "recordings" / "spikes.csv").exists()
