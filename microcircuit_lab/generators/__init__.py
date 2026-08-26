"""Reference-model integrations and shared model mathematics.

Each model package translates model-specific source data into the generic
configuration consumed by :mod:`microcircuit_lab.network` and :mod:`microcircuit_lab.simulation`.
"""

from __future__ import annotations

from typing import Callable
import argparse

from microcircuit_lab.generators.humam.generator import add_cli as _add_humam_cli
from microcircuit_lab.generators.pd14.generator import add_cli as _add_pd14_cli

#: Registered config-generation CLIs, keyed by model name. Each value adds
#: that model's arguments to a ``scripts/generate.py`` subparser. Add new
#: models here so they show up in ``python scripts/generate.py --help``.
MODEL_GENERATORS: dict[str, Callable[[argparse.ArgumentParser], None]] = {
    "humam": _add_humam_cli,
    "pd14": _add_pd14_cli,
}

__all__ = ["MODEL_GENERATORS"]
