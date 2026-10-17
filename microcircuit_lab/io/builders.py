"""
Find the model builders that ``scripts/generate.py`` can run.

A builder is any package with a callable ``main(argv=None)``; ``main`` is
all the shared CLI needs, and how it parses its arguments or splits its
code up is the builder's business. Builders are looked up in two places:

* the ``builders/`` folder of the repository you run from -- every
  subpackage with a ``main`` is found, so adding a model means adding a
  folder and nothing else;
* installed packages that register a ``main`` under the
  ``microcircuit_lab.builders`` entry-point group in their
  ``pyproject.toml``, for builders that live outside this repository::

      [project.entry-points."microcircuit_lab.builders"]
      my_model = "my_package.my_model:main"

The core never imports a builder itself, so it runs with none installed.
A builder that fails to import raises here instead of silently
disappearing. A name found in the folder wins over the same name from an
entry point.
"""

from __future__ import annotations

import importlib
import pkgutil
import sys
from collections.abc import Callable
from importlib.metadata import entry_points
from pathlib import Path

ENTRY_POINT_GROUP = "microcircuit_lab.builders"


def discover_builders(
    builders_dir: str | Path = "builders",
) -> dict[str, Callable[[list[str] | None], None]]:
    """Return ``{model_name: main}`` for every builder found."""

    found: dict[str, Callable[[list[str] | None], None]] = {}

    folder = Path(builders_dir).resolve()
    if folder.is_dir():
        if str(folder.parent) not in sys.path:
            sys.path.insert(0, str(folder.parent))

        for module_info in pkgutil.iter_modules([str(folder)]):
            if not module_info.ispkg:
                continue

            package = importlib.import_module(f"{folder.name}.{module_info.name}")
            main = getattr(package, "main", None)
            if callable(main):
                found[module_info.name] = main

    for entry_point in entry_points(group=ENTRY_POINT_GROUP):
        found.setdefault(entry_point.name, entry_point.load())

    return found
