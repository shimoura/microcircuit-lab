"""Tests for Simulation's choice of backend, its generic backend_options passthrough and
NestBackend's extension_modules use of it (for loading compiled
NEST/NESTML models before the network is built).

nest's module object rejects attribute assignment (nest.Install = ...
raises), so NestBackend's own use of nest.Install() is tested by
monkeypatching the `nest` name inside microcircuit_lab.backends.nest.simulator
(a plain module, not the real nest package) instead of the real nest module.
"""

import numpy as np

import microcircuit_lab.backends.nest.simulator as nest_backend_module
import microcircuit_lab.simulation as runner_module
from microcircuit_lab import Simulation
from microcircuit_lab.backends.nest.simulator import NestBackend
from microcircuit_lab.config.simulation import SimulationConfig
from microcircuit_lab.yaml_files import read_yaml


class _FakeBackend:
    """Records what Simulation.run() constructs it with; does nothing else."""

    last_kwargs: dict | None = None

    def __init__(self, network, simulation_config, **kwargs):
        _FakeBackend.last_kwargs = kwargs

    def version(self):
        return "fake"

    def num_processes(self):
        return 1

    def rank(self):
        return 0

    def sync_processes(self):
        pass

    def prepare_output(self, run_dir):
        pass

    def build(self):
        pass

    def simulate(self):
        pass

    def print_statistics(self):
        pass

    def get_population(self, name):
        # write_run_metadata() reads first_gid off this unconditionally;
        # the actual node IDs are irrelevant to what these tests check.
        return np.array([1])

    def get_spike_events(self, population):
        return {"senders": [], "times": []}

    def save_recordings(self, run_dir):
        return []


def _use_tmp_output(simulation, tmp_path):
    simulation.simulation_config = simulation.simulation_config.model_copy(
        update={
            "output": simulation.simulation_config.output.model_copy(
                update={"output_dir": tmp_path, "overwrite": True}
            )
        }
    )
    return simulation


def test_run_forwards_backend_options_to_the_backend_constructor(monkeypatch, tmp_path):
    monkeypatch.setattr(runner_module, "get_backend", lambda name: _FakeBackend)

    simulation = Simulation.from_yaml(
        network_name="toy",
        simulation_name="toy",
        backend_options={"extension_modules": ["some_module"]},
    )
    _use_tmp_output(simulation, tmp_path)
    simulation.run()

    assert _FakeBackend.last_kwargs == {"extension_modules": ["some_module"]}


def test_run_without_backend_options_forwards_nothing_extra(monkeypatch, tmp_path):
    monkeypatch.setattr(runner_module, "get_backend", lambda name: _FakeBackend)

    simulation = Simulation.from_yaml(network_name="toy", simulation_name="toy")
    _use_tmp_output(simulation, tmp_path)
    simulation.run()

    assert _FakeBackend.last_kwargs == {}


def test_the_simulation_file_chooses_the_backend_and_an_argument_overrides_it(monkeypatch, tmp_path):
    chosen = []
    monkeypatch.setattr(runner_module, "get_backend", lambda name: chosen.append(name) or _FakeBackend)
    profile = SimulationConfig(backend={"name": "brian2", "options": {"device": "cpp_standalone"}})
    network = Simulation.from_yaml(network_name="toy").network

    simulation = _use_tmp_output(Simulation(network, profile, backend_options={"codegen_target": "numpy"}), tmp_path)
    simulation.run()
    assert chosen == ["brian2"]
    assert _FakeBackend.last_kwargs == {"device": "cpp_standalone", "codegen_target": "numpy"}
    # The run's config.yaml records the simulator used.
    saved = read_yaml(simulation.output_dir / "config.yaml")["simulation"]["backend"]
    assert saved == {"name": "brian2", "options": {"device": "cpp_standalone", "codegen_target": "numpy"}}

    # The profile's options belong to Brian2, so NEST does not get them.
    simulation = _use_tmp_output(Simulation(network, profile, backend="nest"), tmp_path)
    simulation.run()
    assert chosen[-1] == "nest"
    assert _FakeBackend.last_kwargs == {}


class _FakeNest:
    """Stands in for the real `nest` module inside NestBackend.initialize(),
    recording Install() calls without needing a real compiled module."""

    def __init__(self):
        self.installed: list[str] = []

    def ResetKernel(self):
        pass

    def Install(self, module):
        self.installed.append(module)

    def set(self, **kwargs):
        pass


def test_initialize_installs_configured_extension_modules(monkeypatch):
    fake_nest = _FakeNest()
    monkeypatch.setattr(nest_backend_module, "nest", fake_nest)

    simulation = Simulation.from_yaml(network_name="toy", simulation_name="toy")
    backend = NestBackend(
        network=simulation.network,
        simulation_config=simulation.simulation_config,
        extension_modules=["module_a", "module_b"],
    )

    backend.initialize()

    assert fake_nest.installed == ["module_a", "module_b"]


def test_initialize_installs_nothing_by_default(monkeypatch):
    fake_nest = _FakeNest()
    monkeypatch.setattr(nest_backend_module, "nest", fake_nest)

    simulation = Simulation.from_yaml(network_name="toy", simulation_name="toy")
    backend = NestBackend(
        network=simulation.network,
        simulation_config=simulation.simulation_config,
    )

    backend.initialize()

    assert fake_nest.installed == []
