"""Interface implemented by simulator backends."""

from __future__ import annotations

from typing import Protocol

from microcircuit_lab.core.config.simulation import SimulationConfig
from microcircuit_lab.core.network import Network


class SimulationBackend(Protocol):
    """Minimal contract required by the simulation orchestrator."""

    def __init__(self, network: Network, simulation_config: SimulationConfig) -> None: ...
    def build(self) -> None: ...
    def simulate(self) -> None: ...
    def print_statistics(self) -> None: ...
