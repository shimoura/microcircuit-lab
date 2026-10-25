"""Interface implemented by simulator backends."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.config.simulation import SimulationConfig


class SimulationBackend(Protocol):
    """
    What ``Simulation.run()`` needs from a simulator.

    ``__init__`` may take extra keyword-only arguments that only that backend
    uses (e.g. NestBackend's ``nest_modules``); ``Simulation`` passes its
    ``backend_options`` through unchanged.
    """

    def __init__(self, network: NetworkConfig, simulation_config: SimulationConfig) -> None: ...

    # Running

    def prepare_output(self, run_dir: Path) -> None:
        """Called before ``build()`` when outputs are saved: a backend that can
        record straight to disk sets that up here; others may do nothing."""
        ...

    def check(self) -> None:
        """Raise if the network names something this simulator does not have
        (a model, a rule, ...). ``Simulation.run()`` calls it before the run
        folder is made and the network built, so a wrong name fails at once."""
        ...

    def build(self) -> None: ...

    def simulate(self) -> None: ...

    def print_statistics(self) -> None: ...

    # MPI processes (without MPI: one process, rank 0, nothing to wait for)

    def version(self) -> str | None:
        """The simulator's version, for the run's metadata."""
        ...

    def num_processes(self) -> int: ...

    def rank(self) -> int: ...

    def sync_processes(self) -> None:
        """Wait until every process gets here."""
        ...

    # Results

    def get_population(self, name: str) -> Any: ...

    def get_spike_events(self, population: str) -> dict: ...

    def save_recordings(self, run_dir: Path) -> list[Path]:
        """Save the recordings under ``run_dir`` and return the files."""
        ...
