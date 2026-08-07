"""Tests for simulation run output writing (recordings, config, metadata)."""

import json
from pathlib import Path

import yaml

from microcircuit_lab.config.simulation import OutputConfig, SimulationConfig
from microcircuit_lab.io.config import NetworkConfigLoader
from microcircuit_lab.io.files import read_network_directory
from microcircuit_lab.io.output import (
    register_artifact,
    resolve_run_directory,
    save_run_outputs,
)
from microcircuit_lab.network import Network, NetworkPreprocessor
from microcircuit_lab.backends.nest import NestBackend


def _toy_network() -> Network:
    network_files = read_network_directory("configs/network/toy")
    config = NetworkConfigLoader(network_files).build()
    config = NetworkPreprocessor(config).process()
    return Network(config)


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

    for sr in backend.spike_recorders.values():
        assert sr.get("record_to") == "ascii"

    backend.simulate()

    # Files already exist on disk, written natively by NEST -- not by us.
    dat_files = sorted((tmp_path / "recordings").glob("E-*.dat"))
    assert dat_files

    events = backend.get_spike_events("E")
    assert len(events["times"]) > 0
    assert len(events["times"]) == len(events["senders"])

    saved = backend.save_recordings(tmp_path)
    assert set(saved) == set((tmp_path / "recordings").glob("[EI]-*.dat"))


def test_memory_mode_fallback_writes_csv_when_no_prepare_output(tmp_path: Path) -> None:
    """Without prepare_output(), the backend keeps its default NEST
    in-memory recording and save_recordings() falls back to a CSV export."""

    network = _toy_network()
    simulation_config = SimulationConfig.model_validate(
        {"t_sim": 200.0, "local_num_threads": 4, "print_time": False}
    )

    backend = NestBackend(network=network, simulation_config=simulation_config)
    backend.build()

    for sr in backend.spike_recorders.values():
        assert sr.get("record_to") == "memory"

    backend.simulate()

    for path in backend.save_recordings(tmp_path):
        rows = path.read_text().splitlines()
        assert rows[0] == "sender,time_ms"
        assert len(rows) > 1


def test_voltage_recording_writes_native_ascii_files(tmp_path: Path) -> None:
    network = _toy_network()
    simulation_config = SimulationConfig.model_validate(
        {
            "t_sim": 100.0,
            "local_num_threads": 2,
            "print_time": False,
            "recording": {"spike_recording": True, "voltage_recording": True, "voltage_interval": 1.0},
        }
    )

    backend = NestBackend(network=network, simulation_config=simulation_config)
    backend.prepare_output(tmp_path)
    backend.build()
    backend.simulate()

    voltage_files = sorted((tmp_path / "recordings").glob("E_voltage-*.dat"))
    assert voltage_files
    content = voltage_files[0].read_text()
    assert "V_m" in content

    saved = backend.save_recordings(tmp_path)
    assert any("voltage" in str(path) for path in saved)


def test_voltage_recording_gate_covers_voltage_only_configs(tmp_path: Path) -> None:
    """save_run_outputs must persist recordings even when spike_recording
    is off and only voltage_recording is on."""

    network = _toy_network()
    simulation_config = SimulationConfig.model_validate(
        {
            "t_sim": 100.0,
            "local_num_threads": 2,
            "print_time": False,
            "recording": {"spike_recording": False, "voltage_recording": True},
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

    assert sorted((tmp_path / "recordings").glob("E_voltage-*.dat"))
    metadata = json.loads((tmp_path / "metadata.json").read_text())
    assert any("voltage" in entry for entry in metadata["artifacts"]["recordings"])


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
    assert metadata["microcircuit_lab_version"] == "0.1.0"
    # This test runs inside the microcircuit-lab git repo, so provenance
    # should resolve to a real commit (not just gracefully return None).
    assert metadata["git"] is not None
    assert len(metadata["git"]["commit"]) == 40
    assert isinstance(metadata["git"]["dirty"], bool)


def test_save_run_outputs_writes_config_and_metadata(tmp_path: Path) -> None:
    network = _toy_network()
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

    assert sorted((tmp_path / "recordings").glob("E-*.dat"))
    assert sorted((tmp_path / "recordings").glob("I-*.dat"))

    config_path = tmp_path / "config.yaml"
    assert config_path.exists()
    saved_config = yaml.safe_load(config_path.read_text())
    assert "network" in saved_config
    assert "simulation" in saved_config
    assert saved_config["network"]["populations"]["E"]["size"] == 800

    metadata_path = tmp_path / "metadata.json"
    assert metadata_path.exists()
    metadata = json.loads(metadata_path.read_text())
    assert metadata["network_name"] == "toy"
    assert metadata["populations"]["E"]["size"] == 800
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
