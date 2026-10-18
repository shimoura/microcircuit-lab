"""Interface implemented by simulator backends."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from microcircuit_lab.config.simulation import SimulationConfig
from microcircuit_lab.config.network import NetworkConfig


class SimulationBackend(Protocol):
    """
    Minimal contract required by the simulation orchestrator.

    A concrete backend's ``__init__`` may accept additional keyword-only
    arguments beyond the two declared here, for whatever that backend
    alone needs (e.g. NestBackend's ``extension_modules``, for loading
    compiled NEST/NESTML extensions). Simulation.run() forwards its
    ``backend_options`` dict as ``**kwargs`` without interpreting it, so
    those arguments are entirely between the caller and the chosen
    backend; this Protocol, and the rest of microcircuit_lab, never
    needs to know about them.
    """

    def __init__(self, network: NetworkConfig, simulation_config: SimulationConfig) -> None: ...

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
