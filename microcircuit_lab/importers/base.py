from abc import ABC, abstractmethod

from microcircuit_lab.config.network import NetworkConfig


class NetworkImporter(ABC):
    """
    Import an external network representation and return a
    validated NetworkConfig.
    """

    @abstractmethod
    def build(self) -> NetworkConfig:
        pass