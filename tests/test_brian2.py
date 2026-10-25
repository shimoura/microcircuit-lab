"""Tests for the Brian2 simulator backend.

The networks use the models in ``models/brian2/``, found from the folder the
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
from microcircuit_lab.config.scaling import ScalingConfig
from microcircuit_lab.config.simulation import SimulationConfig
from microcircuit_lab.config.stimuli import DcStimulusConfig

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("brian2") is None,
    reason="brian2 is not installed",
)

# Found by the test that passes this module in model_modules.
pacemaker = NeuronModel(
    name="pacemaker",
    equations="dV_m/dt = (E_L - V_m)/tau_m : volt\nE_L : volt\ntau_m : second\nI_e : amp",
    threshold="V_m > -55*mV",
    reset="V_m = -70*mV",
    refractory="0*ms",
    excitatory="V_m",
    inhibitory="V_m",
    defaults={"E_L": -50.0, "tau_m": 10.0, "V_m": -70.0},
)


# Found by the tests of project rules and distributions, with pacemaker above.
ring = ConnectionRule(name="ring", condition="abs(index_pre - index_post) <= width")
by_target = Distribution(name="by_target", expression="mean * (1 + index_post) * step", redraw_rounds=0)
alternating = Distribution(name="alternating", expression="mean * (1 - 2*(index_post % 2))", redraw_rounds=0)
no_rounds = Distribution(name="no_rounds", expression="mean")


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


def _network(neuron_model: str, connections=(), stimuli=(), size: int = 50) -> NetworkConfig:
    neuron = NeuronConfig(name="plain", model=neuron_model, parameters=NeuronParams())
    populations = {
        "S": PopulationConfig(name="S", size=2 * size, neuron=neuron),
        "T": PopulationConfig(name="T", size=size, neuron=neuron),
    }
    return NetworkConfig(
        populations=populations,
        connections=list(connections),
        background_inputs={},
        stimuli=list(stimuli),
        scaling=ScalingConfig(),
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
        weight=WeightDistribution(mean=10.0, rel_std=0.0, distribution="fixed", unit="PSC"),
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
        weight=WeightDistribution(mean=10.0, rel_std=0.0, distribution="fixed", unit="PSC"),
        delay=DelayDistribution(mean=1.0, rel_std=0.0, distribution="fixed"),
    )
    backend = _backend(_network("iaf_psc_exp", connections=[connection]), model_modules=[__name__])
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
        WeightDistribution(mean=2.0, rel_std=0.0, unit="PSC", distribution="by_target", parameters={"step": 0.5}),
        DelayDistribution(mean=1.0, rel_std=0.0, distribution="by_target", parameters={"step": 0.1}),
    )
    shared = _row("T", "T", WeightDistribution(mean=7.0, rel_std=0.0, distribution="fixed", unit="PSC"), fixed_delay)
    backend = _backend(_network("iaf_psc_exp", connections=[project, shared]), model_modules=[__name__])
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
    weight = WeightDistribution(mean=3.0, rel_std=0.0, unit="PSC", distribution="alternating")
    connection = _row("S", "T", weight, DelayDistribution(mean=1.0, rel_std=0.0, distribution="fixed"))
    backend = _backend(_network("iaf_psc_exp", connections=[connection]), model_modules=[__name__])
    backend.build()

    import brian2 as b2

    w = backend.synapses[0].w_syn[:] / b2.pA
    odd = (backend.synapses[0].j[:] - 100) % 2 == 1
    assert np.all(w[odd] == 0.0) and np.allclose(w[~odd], 3.0)


def test_redraw_needs_the_distributions_redraw_rounds() -> None:
    weight = WeightDistribution(mean=3.0, rel_std=0.0, unit="PSC", distribution="no_rounds")
    connection = _row("S", "T", weight, DelayDistribution(mean=1.0, rel_std=0.0, distribution="fixed"))
    network = _network("iaf_psc_exp", connections=[connection])
    with pytest.raises(ValueError, match="'no_rounds' has no redraw_rounds.*bound_mode: clip"):
        _backend(network, model_modules=[__name__]).check()

    _backend(network.model_copy(update={"bound_mode": "clip"}), model_modules=[__name__]).check()


def test_an_unknown_rule_says_where_to_define_it() -> None:
    connection = ConnectionConfig(
        source="S",
        target="T",
        rule="no_such_rule",
        weight=WeightDistribution(mean=10.0, rel_std=0.0, distribution="fixed", unit="PSC"),
        delay=DelayDistribution(mean=1.0, rel_std=0.0, distribution="fixed"),
    )
    backend = _backend(_network("iaf_psc_exp", connections=[connection]))
    with pytest.raises(ValueError, match=r"no connection rule 'no_such_rule'.*ConnectionRule.*models/brian2/"):
        backend.check()


def test_redraw_keeps_the_sign_of_the_weights() -> None:
    connection = ConnectionConfig(
        source="S",
        target="T",
        rule="fixed_indegree",
        indegree=20,
        weight=WeightDistribution(mean=-10.0, rel_std=1.0, distribution="normal", unit="PSC"),
        delay=DelayDistribution(mean=1.0, rel_std=0.0, distribution="fixed"),
    )
    backend = _backend(_network("iaf_psc_exp", connections=[connection]))
    backend.build()

    weights = np.asarray(backend.synapses[0].w_syn[:] / 1e-12)
    assert weights.max() < 0.0
    # Redrawn, not clipped: about 16 % of them would be 0 after clipping.
    assert abs(weights.mean() + 10.0 * 1.29) < 1.0


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
    backend = _backend(_network("pacemaker", size=5), model_modules=[__name__])
    backend.build()
    backend.simulate()

    assert len(backend.get_spike_events("T")["times"]) > 0


def test_missing_model_fails_before_the_run_folder_and_says_where_to_define_it(tmp_path: Path) -> None:
    config = SimulationConfig(output={"output_dir": tmp_path / "runs"}, backend={"name": "brian2", "options": NUMPY})
    simulation = Simulation(network=_network("no_such_model"), simulation_config=config, network_name="n")
    with pytest.raises(ValueError, match=r"no neuron model 'no_such_model'.*models/brian2/.*--model-modules"):
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
