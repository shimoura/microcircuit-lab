"""
Find the code of the project you run from: its builders and its analyses.

:func:`discover_builders` finds what ``microcircuit-lab generate`` can run;
:func:`microcircuit_lab.analysis.run_command_plots.discover_plots` finds the plots in
``analyses/``. Both import a folder of the project with
:func:`import_folder_modules`.

A builder is any package with a callable ``main(argv=None)``. That is all the
shared command needs; how ``main`` reads its arguments or splits its code up
is the builder's business. Builders are looked up in two places:

* the ``builders/`` folder of the repository you run from: every
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
from types import ModuleType

BUILDER_ENTRY_POINT_GROUP = "microcircuit_lab.builders"


def import_folder_modules(
    folder: str | Path, *, packages_only: bool = False
) -> dict[str, ModuleType]:
    """Import every module and package in ``folder`` and return them by name.

    The folder's parent is added to the front of ``sys.path``, as Python
    does for the folder of a script you run, so the folder itself is
    importable (``builders.pd14``) and your project's files win over an
    installed package of the same name. With ``packages_only`` plain ``.py``
    files are skipped. An error raised while importing propagates, so a
    broken module fails loudly instead of silently disappearing. A folder
    that does not exist gives ``{}``.
    """

    folder = Path(folder).resolve()
    if not folder.is_dir():
        return {}

    if str(folder.parent) not in sys.path:
        sys.path.insert(0, str(folder.parent))

    modules: dict[str, ModuleType] = {}
    for module_info in pkgutil.iter_modules([str(folder)]):
        if packages_only and not module_info.ispkg:
            continue
        modules[module_info.name] = importlib.import_module(f"{folder.name}.{module_info.name}")
    return modules


def discover_builders(
    builders_dir: str | Path = "builders",
) -> dict[str, Callable[[list[str] | None], None]]:
    """
    Every builder ``microcircuit-lab generate`` can run.

    Parameters
    ----------
    builders_dir
        The project's builders folder. A builder there wins over an installed
        one with the same name.

    Returns
    -------
    dict
        ``{model name: main function}``.
    """

    found: dict[str, Callable[[list[str] | None], None]] = {}

    for name, package in import_folder_modules(builders_dir, packages_only=True).items():
        main = getattr(package, "main", None)
        if callable(main):
            found[name] = main

    for entry_point in entry_points(group=BUILDER_ENTRY_POINT_GROUP):
        found.setdefault(entry_point.name, entry_point.load())

    return found
