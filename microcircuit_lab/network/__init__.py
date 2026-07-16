"""Backward-compatible network imports. New code should use ``microcircuit_lab.core``."""
from microcircuit_lab.core import Network, NetworkPreprocessor
__all__ = ["Network", "NetworkPreprocessor"]
