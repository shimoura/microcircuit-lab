"""Tests for the minimal toy network template.

This is the smallest complete example of the generic YAML network schema
-- new models can be prototyped by copying configs/network/toy/ directly,
without writing any generator code.
"""

import shutil

import pytest

from microcircuit_lab import Simulation
from microcircuit_lab.backends.nest.simulator import NestBackend
from microcircuit_lab.builder_tools.scaling import scale_network
from microcircuit_lab.config.simulation import SimulationConfig
from microcircuit_lab.network.load import read_network


def test_the_generator_rate_is_the_rate_per_synapse_times_the_indegree():
    network = read_network("configs/network/toy")

    assert network.poisson_background["E"].generator_rate == 8.0 * 1000
    assert network.poisson_background["I"].generator_rate == 8.0 * 1000


@pytest.mark.parametrize("scale", [False, True])
def test_a_network_as_read_or_scaled_runs_its_generator_at_rate_times_indegree(scale):
    # Guards the background rate: the network is simulated as given, with no step in between.
    network = read_network("configs/network/toy")
    if scale:
        network = scale_network(network, N_scaling=0.5, K_scaling=0.5, scaled_from="toy",
            compensate_recurrent_input=False,
        )
    simulation_config = SimulationConfig.model_validate({"t_sim": 5.0, "print_time": False})

    backend = NestBackend(network=network, simulation_config=simulation_config)
    backend.build()

    for name, background in network.poisson_background.items():
        rate = backend.background_generators[name].get("rate")
        assert rate == background.rate * background.indegree
        assert rate > background.rate


def test_simulation_from_yaml_defaults_to_toy():
    simulation = Simulation.from_yaml()

    assert simulation.network.populations["E"].size == 800
    assert simulation.simulation_config.t_sim == 1000.0


def test_simulation_from_yaml_without_a_simulation_file_uses_defaults(tmp_path):
    """A network with no configs/simulation/<name>.yaml still loads -- the
    execution profile falls back to SimulationConfig() defaults, the same way
    a missing configs/analysis/<name>.yaml does."""
    from microcircuit_lab.config.simulation import SimulationConfig

    shutil.copytree("configs/network/toy", tmp_path / "network" / "toy")

    simulation = Simulation.from_yaml(config_dir=tmp_path, network_name="toy")

    assert simulation.simulation_config == SimulationConfig()


def test_simulation_from_yaml_rejects_a_missing_named_profile():
    """A profile named explicitly must exist: a misspelled name must not
    silently run with the defaults."""
    with pytest.raises(FileNotFoundError, match="no_such_profile"):
        Simulation.from_yaml(network_name="toy", simulation_name="no_such_profile")


def test_toy_network_actually_spikes(tmp_path):
    """Regression test: a plausible-looking config can still fail to spike
    if the background drive is too weak. Run briefly and check for output."""

    simulation = Simulation.from_yaml(
        network_name="toy",
        simulation_name="toy",
    )
    simulation.simulation_config = simulation.simulation_config.model_copy(
        update={
            "t_sim": 200.0,
            "print_time": False,
            "output": simulation.simulation_config.output.model_copy(
                update={"output_dir": tmp_path, "overwrite": True}
            ),
        }
    )
    simulation.run()

    for pop_name in simulation.backend.populations:
        events = simulation.backend.get_spike_events(pop_name)
        assert len(events["times"]) > 0, f"population '{pop_name}' produced no spikes"
