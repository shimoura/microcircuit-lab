"""Writing simulation run outputs (recordings, config, metadata).

This is the write-side counterpart to :mod:`microcircuit_lab.io.files`. It
depends only on the generic :class:`~microcircuit_lab.backends.base.SimulationBackend`
contract, never on a specific backend, so it works for any simulator.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from microcircuit_lab.backends.base import SimulationBackend
from microcircuit_lab.config.simulation import OutputConfig, SimulationConfig
from microcircuit_lab.io.files import flow_records, write_yaml
from microcircuit_lab.network import Network


def resolve_run_directory(
    output: OutputConfig,
    *,
    network_name: str,
    simulation_name: str,
) -> Path:
    """
    Resolve and create the directory a simulation run should write to.

    If ``output.overwrite`` is True, every run reuses
    ``output.output_dir`` directly -- convenient while iterating on a
    model. Otherwise each run gets its own ``<output_dir>/<timestamp>``
    subdirectory, so results from different runs are never silently
    overwritten.
    """

    base = Path(output.output_dir)

    if output.overwrite:
        run_dir = base
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = base / timestamp
        suffix = 1
        while run_dir.exists():
            run_dir = base / f"{timestamp}_{suffix}"
            suffix += 1

    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def save_run_config(
    network: Network,
    simulation_config: SimulationConfig,
    run_dir: Path,
) -> Path:
    """Save the fully resolved (preprocessed) network and simulation config.

    connections/populations/background_inputs are written one-record-per-line
    (see io.files.flow_records) since a full-scale network can have
    thousands of connection entries.
    """

    network_payload = network.config.model_dump(mode="json")
    for field in ("connections", "populations", "background_inputs"):
        network_payload[field] = flow_records(network_payload[field])

    payload = {
        "network": network_payload,
        "simulation": simulation_config.model_dump(mode="json"),
    }
    path = run_dir / "config.yaml"
    write_yaml(path, payload)
    return path


def _git_provenance(cwd: Path) -> dict[str, object] | None:
    """
    Best-effort git commit/dirty-tree info for whatever repository ``cwd``
    is in (git searches upward for ``.git`` itself, same as running `git`
    by hand). Returns None if git isn't available or cwd isn't a repo --
    this must never fail a run just because provenance can't be determined.
    """

    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=5,
        )
        if commit.returncode != 0:
            return None

        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd, capture_output=True, text=True, timeout=5,
        )

        return {
            "commit": commit.stdout.strip(),
            "dirty": bool(status.stdout.strip()),
        }
    except (OSError, subprocess.TimeoutExpired):
        return None


def _package_version() -> str | None:
    try:
        return version("microcircuit_lab")
    except PackageNotFoundError:
        return None


def write_run_metadata(
    run_dir: Path,
    *,
    network: Network,
    backend: SimulationBackend,
    simulation_config: SimulationConfig,
    network_name: str,
    simulation_name: str,
    backend_name: str,
) -> Path:
    """Write ``metadata.json``: run identity, per-population spike statistics
    (if spike_recording was enabled), and an ``artifacts`` manifest that
    :func:`register_artifact` appends to."""

    t_sim_s = simulation_config.t_sim / 1000.0
    populations = {}

    for pop_name, pop_cfg in network.config.populations.items():
        stats = {"size": pop_cfg.size}

        if simulation_config.recording.spike_recording:
            n_spikes = len(backend.get_spike_events(pop_name)["times"])
            stats["n_spikes"] = n_spikes
            stats["mean_rate_hz"] = (n_spikes / (pop_cfg.size * t_sim_s)) if pop_cfg.size else 0.0

        populations[pop_name] = stats

    metadata = {
        "network_name": network_name,
        "simulation_name": simulation_name,
        "backend": backend_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "microcircuit_lab_version": _package_version(),
        "git": _git_provenance(Path.cwd()),
        "t_sim_ms": simulation_config.t_sim,
        "rng_seed": simulation_config.rng_seed,
        "populations": populations,
        "artifacts": {},
    }

    path = run_dir / "metadata.json"
    path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return path


def register_artifact(run_dir: Path, category: str, path: str | Path) -> None:
    """
    Record an artifact (e.g. a saved plot) under ``category`` in
    ``metadata.json``, so the run directory carries a single manifest of
    everything it contains instead of requiring callers to glob for files.

    No-op if ``metadata.json`` was not written for this run
    (``output.save_metadata=False``).
    """

    metadata_path = Path(run_dir) / "metadata.json"
    if not metadata_path.exists():
        return

    metadata = json.loads(metadata_path.read_text())
    artifacts = metadata.setdefault("artifacts", {}).setdefault(category, [])

    relative = str(Path(path).resolve().relative_to(Path(run_dir).resolve()))
    if relative not in artifacts:
        artifacts.append(relative)

    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def save_run_outputs(
    *,
    run_dir: Path,
    network: Network,
    simulation_config: SimulationConfig,
    backend: SimulationBackend,
    network_name: str,
    simulation_name: str,
    backend_name: str,
) -> None:
    """
    Save whatever the simulation config requests (recordings, resolved
    config, metadata) into an already-resolved ``run_dir``.

    ``run_dir`` must come from :func:`resolve_run_directory`, called
    *before* ``backend.build()`` so backends that record straight to disk
    (e.g. NEST) can be pointed at it via ``backend.prepare_output()``.
    """

    output = simulation_config.output

    if output.save_metadata:
        write_run_metadata(
            run_dir,
            network=network,
            backend=backend,
            simulation_config=simulation_config,
            network_name=network_name,
            simulation_name=simulation_name,
            backend_name=backend_name,
        )

    recording = simulation_config.recording
    if recording.spike_recording or recording.voltage_recording:
        for path in backend.save_recordings(run_dir):
            register_artifact(run_dir, "recordings", path)

    if output.save_config:
        config_path = save_run_config(network, simulation_config, run_dir)
        register_artifact(run_dir, "config", config_path)
