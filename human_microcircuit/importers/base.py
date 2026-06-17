from abc import ABC, abstractmethod

from human_microcircuit.config.network import NetworkConfig


class NetworkImporter(ABC):
    """
    Import an external network representation and return a
    validated NetworkConfig.
    """

    @abstractmethod
    def build(self) -> NetworkConfig:
        pass