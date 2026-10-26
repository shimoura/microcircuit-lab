"""Write the outputs of a run: recordings, config and metadata.

It uses only the :class:`~microcircuit_lab.backends.interface.SimulationBackend`
interface, so it works with any backend.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from microcircuit_lab.backends.interface import SimulationBackend
from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.config.simulation import OutputConfig, SimulationConfig
from microcircuit_lab.config.yaml_files import flow_records, write_yaml

logger = logging.getLogger(__name__)

# A .run_dir older than this was left by a run that crashed.
STALE_HANDOFF_SECONDS = 60.0


def _base_directory(output: OutputConfig, network_name: str) -> Path:
    return Path(output.output_dir) if output.output_dir else Path("output") / network_name


def share_run_directory(
    output: OutputConfig,
    *,
    network_name: str,
    simulation_name: str,
    backend: SimulationBackend,
) -> Path:
    """
    The run folder, the same on every MPI process.

    With ``overwrite: true`` the folder is fixed, so every process resolves it
    itself. Otherwise process 0 resolves it (:func:`resolve_run_directory`) and
    writes its path to ``<output_dir>/.run_dir/path``; the others read it there
    once all processes have met, and process 0 then deletes ``.run_dir``. The
    simulator provides the meeting point, so no MPI package for Python is needed.

    ``.run_dir`` is made with ``mkdir``, which fails if it exists, also on network
    file systems: a second run into the same ``output_dir`` waits until the first
    has handed its folder over. One older than ``STALE_HANDOFF_SECONDS`` was left
    by a crashed run and is replaced.
    """

    if backend.num_processes() == 1 or output.overwrite:
        return resolve_run_directory(
            output, network_name=network_name, simulation_name=simulation_name
        )

    handoff = _base_directory(output, network_name) / ".run_dir"
    if backend.rank() == 0:
        _claim(handoff)
        run_dir = resolve_run_directory(
            output, network_name=network_name, simulation_name=simulation_name
        )
        (handoff / "path").write_text(str(run_dir), encoding="utf-8")
    backend.sync_processes()
    run_dir = Path((handoff / "path").read_text(encoding="utf-8"))
    backend.sync_processes()
    if backend.rank() == 0:
        shutil.rmtree(handoff)
    return run_dir


def _claim(handoff: Path) -> None:
    """Make the folder ``handoff``, waiting while another run holds it."""

    handoff.parent.mkdir(parents=True, exist_ok=True)
    waited = False
    while True:
        try:
            handoff.mkdir()
            return
        except FileExistsError:
            try:
                age = time.time() - handoff.stat().st_mtime
            except FileNotFoundError:
                continue
            if age > STALE_HANDOFF_SECONDS:
                logger.warning("Removing %s, left by a run that did not finish.", handoff)
                shutil.rmtree(handoff, ignore_errors=True)
                continue
            if not waited:
                logger.info("Waiting for another run to hand over its folder (%s).", handoff)
                waited = True
            time.sleep(0.1)


def resolve_run_directory(
    output: OutputConfig,
    *,
    network_name: str,
    simulation_name: str,
) -> Path:
    """
    Create the folder a run writes to, and return it.

    With ``output.overwrite`` true, every run uses ``output.output_dir`` itself,
    which is convenient while you are still changing the model. Otherwise each
    run gets its own ``<output_dir>/<timestamp>`` folder, so earlier results are
    not overwritten. Without an ``output_dir`` it is ``output/<network_name>``.
    """

    base = _base_directory(output, network_name)
    base.mkdir(parents=True, exist_ok=True)
    if output.overwrite:
        return base

    # mkdir fails if the folder exists, so two runs started in the same second
    # never share one.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = base / timestamp
    suffix = 1
    while True:
        try:
            run_dir.mkdir()
            return run_dir
        except FileExistsError:
            run_dir = base / f"{timestamp}_{suffix}"
            suffix += 1


def save_run_config(
    network: NetworkConfig,
    simulation_config: SimulationConfig,
    run_dir: Path,
) -> Path:
    """Save the network as given and the simulation config.

    connections/populations/poisson_background are written one-record-per-line
    (see config.yaml_files.flow_records) since a full-scale network can have
    thousands of connection entries. Above 20,000 connections,
    they go to ``connections.csv`` instead, named by ``connections_file`` in
    ``config.yaml``.
    """

    network_payload = network.model_dump(mode="json", exclude={"connections"})
    most_connections_in_yaml = 20_000
    if len(network.connections) > most_connections_in_yaml:
        network.connections.write_csv(run_dir / "connections.csv")
        network_payload["connections_file"] = "connections.csv"
    else:
        network_payload["connections"] = flow_records(network.connections.to_yaml_rows())
    for field in ("populations", "poisson_background"):
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
    The git commit and whether the working tree has uncommitted changes, for
    the repository that contains ``cwd``. Returns None if git is not available
    or ``cwd`` is not in a repository, so that a run never fails because of it.
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


def _core_git_provenance() -> dict[str, object] | None:
    """
    Git commit of the core, when it runs from a clone of its repository (an
    editable install). An installed copy has no repository of its own, and
    git would otherwise find the project's.
    """

    package_dir = Path(__file__).resolve().parents[1]
    if not (package_dir.parent / ".git").exists():
        return None
    return _git_provenance(package_dir)


def _package_version() -> str | None:
    try:
        return version("microcircuit_lab")
    except PackageNotFoundError:
        return None


def write_run_metadata(
    run_dir: Path,
    *,
    network: NetworkConfig,
    backend: SimulationBackend,
    simulation_config: SimulationConfig,
    network_name: str,
    simulation_name: str,
    backend_name: str,
) -> Path:
    """Write ``metadata.json``: the run's identity, the spike statistics of each
    population (if spikes were recorded) and a list of the files of the run, to
    which :func:`register_artifact` adds.

    ``first_node_id`` and ``last_node_id`` give the node IDs of each population,
    which are one contiguous block. :func:`~microcircuit_lab.run_folder.read.read_run` uses
    them to read a saved run without simulating it again.
    """

    t_sim_s = simulation_config.t_sim / 1000.0
    populations = {}

    for pop_name, pop_cfg in network.populations.items():
        node_ids = backend.get_population(pop_name).tolist()
        stats = {
            "size": pop_cfg.size,
            "first_node_id": int(node_ids[0]),
            "last_node_id": int(node_ids[-1]),
        }

        if simulation_config.recording.spike_recording:
            n_spikes = len(backend.get_spike_events(pop_name)["times"])
            stats["n_spikes"] = n_spikes
            stats["mean_rate_hz"] = (n_spikes / (pop_cfg.size * t_sim_s)) if pop_cfg.size else 0.0

        populations[pop_name] = stats

    metadata = {
        "network_name": network_name,
        "simulation_name": simulation_name,
        "backend": backend_name,
        "simulator_version": backend.version(),
        "num_processes": backend.num_processes(),
        "created_at": datetime.now(UTC).isoformat(),
        "microcircuit_lab_version": _package_version(),
        "git": _git_provenance(Path.cwd()),
        "core_git": _core_git_provenance(),
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
    List a file in the run's ``metadata.json``, under a category.

    ``metadata.json`` then lists everything a run folder holds, so nobody has
    to search the folder for files. Does nothing if the run has no
    ``metadata.json`` (``save_metadata: false``).

    Parameters
    ----------
    run_dir
        The run folder, e.g. ``simulation.output_dir``.
    category
        The kind of file, e.g. ``"plots"``.
    path
        The file; stored relative to ``run_dir``.
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
    network: NetworkConfig,
    simulation_config: SimulationConfig,
    backend: SimulationBackend,
    network_name: str,
    simulation_name: str,
    backend_name: str,
) -> None:
    """
    Save what the simulation config asks for (recordings, config, metadata)
    in ``run_dir``.

    ``run_dir`` comes from :func:`resolve_run_directory`, which is called before
    ``backend.build()`` so that a backend that records straight to disk (NEST)
    can be pointed at it with ``backend.prepare_output()``.
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
    if recording.spike_recording or recording.variables:
        for path in backend.save_recordings(run_dir):
            register_artifact(run_dir, "recordings", path)

    if output.save_config:
        config_path = save_run_config(network, simulation_config, run_dir)
        register_artifact(run_dir, "config", config_path)
