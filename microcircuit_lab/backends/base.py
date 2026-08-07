"""Interface implemented by simulator backends."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from microcircuit_lab.config.simulation import SimulationConfig
from microcircuit_lab.network import Network


class SimulationBackend(Protocol):
    """Minimal contract required by the simulation orchestrator."""

    def __init__(self, network: Network, simulation_config: SimulationConfig) -> None: ...

    def prepare_output(self, run_dir: Path) -> None:
        """
        Called before :meth:`build`, if the simulation will save outputs.

        Backends that can record directly to disk (e.g. NEST's native
        ascii recording backend) should configure that here, so recording
        never has to buffer the full spike history in Python memory.
        Backends without that capability may no-op and fall back to
        writing recordings from memory in :meth:`save_recordings`.
        """
        ...

    def build(self) -> None: ...
    def simulate(self) -> None: ...
    def print_statistics(self) -> None: ...

    def get_population(self, name: str) -> Any: ...
    def get_spike_events(self, population: str) -> dict: ...

    def save_recordings(self, run_dir: Path) -> list[Path]:
        """Persist recordings under ``run_dir`` and return the files written."""
        ...
