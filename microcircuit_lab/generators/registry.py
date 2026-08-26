"""
Registry of model config-generation CLIs, discovered automatically.

Same registry pattern used elsewhere in this package for "pluggable, named
thing" problems -- simulator backends (microcircuit_lab.backends.get_backend),
bundled analysis diagnostics (microcircuit_lab.analysis.registry.PLOT_REGISTRY),
spectral estimators (power_spectrum.POWER_SPECTRUM_METHODS). Applied to
generators: a subpackage under microcircuit_lab/generators/ is picked up
automatically as long as its generator.py exposes an add_cli(subparser)
function -- no edit to this file needed to add a new model.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import os
import pkgutil
from typing import Callable

#: Directory this file lives in (microcircuit_lab/generators/), scanned for
#: model subpackages. Using the directory directly, rather than importing
#: the microcircuit_lab.generators package here, avoids a self-import of
#: the very package this registry is built for.
_GENERATORS_DIR = os.path.dirname(__file__)


def _has_cli_entry_point(generator_module) -> bool:
    """Check whether a model's ``generator`` module exposes a callable ``add_cli``.

    ``add_cli(subparser)`` is what wires a model into ``scripts/generate.py``;
    a package missing it isn't usable as a generator yet.
    """

    return callable(getattr(generator_module, "add_cli", None))


def _discover_generators() -> dict[str, Callable[[argparse.ArgumentParser], None]]:
    registry: dict[str, Callable[[argparse.ArgumentParser], None]] = {}

    for module_info in pkgutil.iter_modules([_GENERATORS_DIR]):
        if not module_info.ispkg:
            continue

        module_name = f"microcircuit_lab.generators.{module_info.name}.generator"
        if importlib.util.find_spec(module_name) is None:
            # This subpackage has no generator.py at all -- not a model
            # package (e.g. a future data-only or docs-only subfolder).
            continue

        # Any error raised while importing generator.py itself (a bug in
        # that model's code, not "this isn't a model package") is allowed
        # to propagate, so a broken model fails loudly at import time
        # instead of silently vanishing from the registry.
        generator_module = importlib.import_module(module_name)

        if _has_cli_entry_point(generator_module):
            registry[module_info.name] = generator_module.add_cli

    return registry


#: Config-generation CLIs, keyed by model name.
GENERATOR_REGISTRY: dict[str, Callable[[argparse.ArgumentParser], None]] = _discover_generators()
