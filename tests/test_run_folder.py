"""Tests for simulation run output writing (recordings, config, metadata)."""

import json
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pytest
import yaml

from microcircuit_lab.backends.nest.simulator import NestBackend
from microcircuit_lab.backends.nest.spike_files import read_saved_variable
from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.config.simulation import OutputConfig, SimulationConfig
from microcircuit_lab.network.load import assemble_network, read_network_files
from microcircuit_lab.run_folder import read_run
from microcircuit_lab.run_folder.write import (
    register_artifact,
    resolve_run_directory,
    save_run_outputs,
)


def _toy_network() -> NetworkConfig:
    network_files = read_network_files("configs/network/toy")
    config = assemble_network(network_files)
    return config


def test_resolve_run_directory_overwrite_reuses_same_dir(tmp_path: Path) -> None:
    output = OutputConfig(output_dir=tmp_path / "run", overwrite=True)

    first = resolve_run_directory(output, network_name="toy", simulation_name="toy")
    second = resolve_run_directory(output, network_name="toy", simulation_name="toy")

    assert first == second == tmp_path / "run"
    assert first.is_dir()


def test_resolve_run_directory_without_overwrite_never_collides(tmp_path: Path) -> None:
    output = OutputConfig(output_dir=tmp_path / "run", overwrite=False)

    first = resolve_run_directory(output, network_name="toy", simulation_name="toy")
    second = resolve_run_directory(output, network_name="toy", simulation_name="toy")

    assert first != second
    assert first.is_dir()
    assert second.is_dir()
    assert first.parent == second.parent == tmp_path / "run"


def test_resolve_run_directory_defaults_to_the_network_name(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    run_dir = resolve_run_directory(OutputConfig(), network_name="toy", simulation_name="toy")

    assert run_dir.parent == Path("output") / "toy"


def test_native_ascii_recording_writes_directly_to_disk(tmp_path: Path) -> None:
    """
    With prepare_output() called (as Simulation.run() does), NEST's own
    ascii recording backend writes spikes straight to disk during
    simulate() -- microcircuit_lab never buffers or re-serializes them.
    """

    network = _toy_network()
    simulation_config = SimulationConfig.model_validate(
        {"t_sim": 200.0, "local_num_threads": 2, "print_time": False}
    )

    backend = NestBackend(network=network, simulation_config=simulation_config)
    backend.prepare_output(tmp_path)
    backend.build()

    assert backend.spike_recorder.get("record_to") == "ascii"

    backend.simulate()

    # Files already exist on disk, written natively by NEST -- not by us.
    dat_files = sorted((tmp_path / "recordings").glob("spikes-*.dat"))
    assert dat_files

    events = backend.get_spike_events("E")
    assert len(events["times"]) > 0
    assert len(events["times"]) == len(events["senders"])

    saved = backend.save_recordings(tmp_path)
    assert set(saved) == set((tmp_path / "recordings").glob("spikes-*.dat"))


def test_memory_mode_fallback_writes_csv_when_no_prepare_output(tmp_path: Path) -> None:
    """Without prepare_output(), the backend keeps its default NEST
    in-memory recording and save_recordings() falls back to a CSV export."""

    network = _toy_network()
    simulation_config = SimulationConfig.model_validate(
        {"t_sim": 200.0, "local_num_threads": 4, "print_time": False}
    )

    backend = NestBackend(network=network, simulation_config=simulation_config)
    backend.build()

    assert backend.spike_recorder.get("record_to") == "memory"

    backend.simulate()

    for path in backend.save_recordings(tmp_path):
        rows = path.read_text().splitlines()
        assert rows[0] == "sender,time_ms"
        assert len(rows) > 1


def test_variables_are_written_as_native_ascii_files(tmp_path: Path) -> None:
    network = _toy_network()
    simulation_config = SimulationConfig.model_validate(
        {
            "t_sim": 100.0,
            "local_num_threads": 2,
            "print_time": False,
            "recording": {
                "spike_recording": True,
                "variables": {"V_m": {"interval": 1.0}, "I_syn_ex": {"interval": 2.0}},
            },
        }
    )

    backend = NestBackend(network=network, simulation_config=simulation_config)
    backend.prepare_output(tmp_path)
    backend.build()
    backend.simulate()

    for name in ("V_m", "I_syn_ex"):
        files = sorted((tmp_path / "recordings").glob(f"{name}-*.dat"))
        assert files
        assert name in files[0].read_text()

    saved = backend.save_recordings(tmp_path)
    assert any("V_m-" in str(path) for path in saved)
    assert any("I_syn_ex-" in str(path) for path in saved)


def test_variables_gate_covers_configs_without_spikes(tmp_path: Path) -> None:
    """save_run_outputs must persist recordings even when spike_recording
    is off and only variables are recorded."""

    network = _toy_network()
    simulation_config = SimulationConfig.model_validate(
        {
            "t_sim": 100.0,
            "local_num_threads": 2,
            "print_time": False,
            "recording": {"spike_recording": False, "variables": {"V_m": {}}},
            "output": {"output_dir": str(tmp_path), "overwrite": True},
        }
    )

    backend = NestBackend(network=network, simulation_config=simulation_config)
    backend.prepare_output(tmp_path)
    backend.build()
    backend.simulate()

    save_run_outputs(
        run_dir=tmp_path,
        network=network,
        simulation_config=simulation_config,
        backend=backend,
        network_name="toy",
        simulation_name="toy",
        backend_name="nest",
    )

    assert sorted((tmp_path / "recordings").glob("V_m-*.dat"))
    metadata = json.loads((tmp_path / "metadata.json").read_text())
    assert any("V_m" in entry for entry in metadata["artifacts"]["recordings"])

    senders, times, values = read_run(tmp_path).recording("V_m")
    assert len(senders) == len(times) == len(values) > 0
    assert (np.diff(senders) >= 0).all()


def test_metadata_includes_provenance(tmp_path: Path) -> None:
    network = _toy_network()
    simulation_config = SimulationConfig.model_validate(
        {
            "t_sim": 100.0,
            "local_num_threads": 2,
            "print_time": False,
            "output": {"output_dir": str(tmp_path), "overwrite": True},
        }
    )

    backend = NestBackend(network=network, simulation_config=simulation_config)
    backend.prepare_output(tmp_path)
    backend.build()
    backend.simulate()

    save_run_outputs(
        run_dir=tmp_path,
        network=network,
        simulation_config=simulation_config,
        backend=backend,
        network_name="toy",
        simulation_name="toy",
        backend_name="nest",
    )

    metadata = json.loads((tmp_path / "metadata.json").read_text())
    assert metadata["microcircuit_lab_version"] == version("microcircuit_lab")
    # This test runs inside the microcircuit-lab git repo, so provenance
    # should resolve to a real commit (not just gracefully return None).
    assert metadata["git"] is not None
    assert len(metadata["git"]["commit"]) == 40
    assert isinstance(metadata["git"]["dirty"], bool)


def test_core_git_provenance_only_for_a_clone_of_the_core(tmp_path: Path, monkeypatch) -> None:
    from microcircuit_lab.run_folder import write as run_folder

    # The test suite runs from a clone of the repository.
    assert len(run_folder._core_git_provenance()["commit"]) == 40

    # An installed copy (no .git next to the package) has no commit of its own.
    package_file = tmp_path / "site-packages" / "microcircuit_lab" / "run_folder" / "write.py"
    monkeypatch.setattr(run_folder, "__file__", str(package_file))
    assert run_folder._core_git_provenance() is None


def test_save_run_outputs_writes_config_and_metadata(tmp_path: Path) -> None:
    network = _toy_network()
    expected_size = network.populations["E"].size
    simulation_config = SimulationConfig.model_validate(
        {
            "t_sim": 200.0,
            "local_num_threads": 4,
            "print_time": False,
            "output": {"output_dir": str(tmp_path), "overwrite": True},
        }
    )

    backend = NestBackend(network=network, simulation_config=simulation_config)
    backend.prepare_output(tmp_path)
    backend.build()
    backend.simulate()

    save_run_outputs(
        run_dir=tmp_path,
        network=network,
        simulation_config=simulation_config,
        backend=backend,
        network_name="toy",
        simulation_name="toy",
        backend_name="nest",
    )

    assert sorted((tmp_path / "recordings").glob("spikes-*.dat"))

    config_path = tmp_path / "config.yaml"
    assert config_path.exists()
    saved_config = yaml.safe_load(config_path.read_text())
    assert "network" in saved_config
    assert "simulation" in saved_config
    assert saved_config["network"]["populations"]["E"]["size"] == expected_size

    metadata_path = tmp_path / "metadata.json"
    assert metadata_path.exists()
    metadata = json.loads(metadata_path.read_text())
    assert metadata["network_name"] == "toy"
    assert metadata["populations"]["E"]["size"] == expected_size
    assert metadata["populations"]["E"]["n_spikes"] > 0
    assert metadata["artifacts"]["recordings"]
    assert all(
        entry.startswith("recordings/") for entry in metadata["artifacts"]["recordings"]
    )
    assert metadata["artifacts"]["config"] == ["config.yaml"]


def test_register_artifact_appends_and_is_noop_without_metadata(tmp_path: Path) -> None:
    plot_path = tmp_path / "plots" / "raster.png"
    plot_path.parent.mkdir()
    plot_path.write_text("not a real png")

    # No metadata.json written for this run -> silently does nothing.
    register_artifact(tmp_path, "plots", plot_path)
    assert not (tmp_path / "metadata.json").exists()

    (tmp_path / "metadata.json").write_text(json.dumps({"artifacts": {}}))
    register_artifact(tmp_path, "plots", plot_path)
    register_artifact(tmp_path, "plots", plot_path)  # idempotent

    metadata = json.loads((tmp_path / "metadata.json").read_text())
    assert metadata["artifacts"]["plots"] == ["plots/raster.png"]


def test_variable_sample_size_and_populations(tmp_path: Path) -> None:
    """sample_size records the first N neurons of each listed population."""

    network = _toy_network()
    simulation_config = SimulationConfig.model_validate(
        {
            "t_sim": 50.0,
            "local_num_threads": 1,
            "print_time": False,
            "recording": {
                "spike_recording": False,
                "variables": {"V_m": {"sample_size": 3}},
            },
        }
    )

    backend = NestBackend(network=network, simulation_config=simulation_config)
    backend.prepare_output(tmp_path)
    backend.build()
    backend.simulate()

    senders, _, _ = read_saved_variable(tmp_path / "recordings", "V_m")
    assert set(senders) == {1, 2, 3, 801, 802, 803}


def test_unknown_recorded_population_fails(tmp_path: Path) -> None:
    network = _toy_network()
    simulation_config = SimulationConfig.model_validate(
        {"recording": {"variables": {"V_m": {"populations": ["no_such_population"]}}}}
    )
    backend = NestBackend(network=network, simulation_config=simulation_config)
    with pytest.raises(ValueError, match="unknown population.*no_such_population"):
        backend.build()


def test_voltage_fields_were_removed() -> None:
    with pytest.raises(ValueError, match=r"voltage_recording.*variables: \{V_m"):
        SimulationConfig.model_validate({"recording": {"voltage_recording": True}})


def test_a_run_folder_is_read_back(tmp_path: Path) -> None:
    from microcircuit_lab.simulation import Simulation

    network = _toy_network()
    simulation_config = SimulationConfig.model_validate(
        {
            "t_sim": 100.0,
            "local_num_threads": 2,
            "print_time": False,
            "output": {"output_dir": str(tmp_path), "overwrite": True},
        }
    )

    sim = Simulation(
        network=network,
        simulation_config=simulation_config,
        backend="nest",
        network_name="toy",
        simulation_name="toy",
    )
    sim.run()

    run = read_run(tmp_path)

    assert run.populations == list(network.populations)
    assert run.simulation.t_sim == 100.0
    assert run.metadata["backend"] == "nest"
    for population in run.populations:
        live = sim.backend.get_spike_events(population)
        saved = run.spikes(population)
        np.testing.assert_array_equal(saved.senders, live["senders"])
        np.testing.assert_array_equal(saved.times, live["times"])
        np.testing.assert_array_equal(
            run.node_ids(population), sim.backend.get_population(population).tolist()
        )



def test_only_the_first_mpi_process_saves(tmp_path: Path, monkeypatch) -> None:
    """A second MPI process takes the run folder process 0 wrote to ``.run_dir/path``,
    simulates, and writes nothing (no folder of its own, no metadata, no config)."""
    import microcircuit_lab.simulation as runner_module
    from microcircuit_lab.simulation import Simulation

    class _SecondProcess(NestBackend):
        def num_processes(self):
            return 2

        def rank(self):
            return 1

        def sync_processes(self):
            pass

    base = tmp_path / "output"
    shared_dir = base / "chosen_by_process_0"
    shared_dir.mkdir(parents=True)
    (base / ".run_dir").mkdir()
    (base / ".run_dir" / "path").write_text(str(shared_dir))
    monkeypatch.setattr(runner_module, "get_backend", lambda name: _SecondProcess)
    simulation_config = SimulationConfig.model_validate(
        {
            "t_sim": 50.0,
            "print_time": False,
            "output": {"output_dir": str(base), "overwrite": False},
        }
    )
    sim = Simulation(network=_toy_network(), simulation_config=simulation_config)
    sim.run()

    assert not sim.is_main_process
    assert sim.output_dir == shared_dir
    assert sorted(path.name for path in base.iterdir()) == [".run_dir", "chosen_by_process_0"]
    assert not (shared_dir / "metadata.json").exists()
    assert not (shared_dir / "config.yaml").exists()
