"""Reference-model integrations and shared model mathematics.

Each model package translates model-specific source data into the generic
configuration consumed by :mod:`microcircuit_lab.network` and :mod:`microcircuit_lab.simulation`.
"""

from __future__ import annotations

from microcircuit_lab.generators.registry import GENERATORS, discover_generators

__all__ = ["GENERATORS", "discover_generators"]
