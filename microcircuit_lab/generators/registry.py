"""
Automatic discovery of model generators.

A generator is any subpackage of ``microcircuit_lab/generators/`` whose
package exposes a callable ``main(argv=None)``. Discovery imports each
subpackage and keeps the ones that do -- there is no list to edit here
and nothing to register when a model is added.

``main`` is the only hook the shared CLI needs: ``scripts/generate.py
<name> ...`` calls ``<package>.main(remaining_args)``. How a generator
splits its own code up, and how ``main`` parses its arguments (argparse,
something else, or nothing), is entirely the generator's business -- the
bundled models keep the logic in a ``build`` module and re-export
``main`` from ``__init__``.

The generator's real contract is its *output*: a directory under
``configs/network/<name>/`` that passes
:func:`microcircuit_lab.io.validate_network_config`.
"""

from __future__ import annotations

import importlib
import os
import pkgutil
from types import ModuleType

#: Directory this file lives in (microcircuit_lab/generators/), scanned for
#: model subpackages. Used directly rather than importing the
#: microcircuit_lab.generators package, to avoid a self-import.
_GENERATORS_DIR = os.path.dirname(__file__)


def discover_generators() -> dict[str, ModuleType]:
    """Return ``{model_name: generator_package}`` for every discoverable model.

    A subpackage qualifies if it exposes a callable ``main``. An error
    raised while importing one propagates -- a broken generator fails
    loudly here rather than silently disappearing.
    """

    found: dict[str, ModuleType] = {}

    for module_info in pkgutil.iter_modules([_GENERATORS_DIR]):
        if not module_info.ispkg:
            continue

        package = importlib.import_module(f"microcircuit_lab.generators.{module_info.name}")
        if callable(getattr(package, "main", None)):
            found[module_info.name] = package

    return found


#: Discovered generator packages, keyed by model name. Built at import
#: time so a broken generator surfaces immediately.
GENERATORS: dict[str, ModuleType] = discover_generators()
