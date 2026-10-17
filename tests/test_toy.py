"""Tests for the minimal toy network template.

This is the smallest complete example of the generic YAML network schema
-- new models can be prototyped by copying configs/network/toy/ directly,
without writing any generator code.
"""

from microcircuit_lab import Simulation
from microcircuit_lab.io.config import NetworkConfigLoader
from microcircuit_lab.io.files import read_network_directory
from microcircuit_lab.network.preprocessing import NetworkPreprocessor


def test_toy_network_loads_and_preprocesses():
    network_files = read_network_directory("configs/network/toy")
    network = NetworkConfigLoader(network_files).build()
    network = NetworkPreprocessor(network).process()

    assert network.populations["E"].size == 800
    assert network.populations["I"].size == 200

    # background rate (Hz) * background_indegree, per NetworkPreprocessor
    assert network.background_inputs["E"].rate == 8.0 * 1000
    assert network.background_inputs["I"].rate == 8.0 * 1000


def test_simulation_from_yaml_defaults_to_toy():
    simulation = Simulation.from_yaml()

    assert simulation.network.config.populations["E"].size == 800
    assert simulation.simulation_config.t_sim == 1000.0


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
