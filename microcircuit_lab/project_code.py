"""
Find the code of the project you run from: its builders, its analyses and its
definitions (models and the like, which the config files name).

:func:`discover_builders` finds what ``microcircuit-lab generate`` can run;
:func:`microcircuit_lab.analysis.run_command_plots.discover_plots` finds the plots in
``analyses/``; :func:`find_definitions` finds the objects a backend looks up by
name, such as the Brian2 models in ``models/brian2/``. All import a folder of the
project with :func:`import_folder_modules`.

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
from collections.abc import Callable, Sequence
from importlib.metadata import entry_points
from pathlib import Path
from types import ModuleType
from typing import Any

BUILDER_ENTRY_POINT_GROUP = "microcircuit_lab.builders"


def import_folder_modules(
    folder: str | Path, *, packages_only: bool = False, package: str | None = None
) -> dict[str, ModuleType]:
    """Import every module and package in ``folder`` and return them by name.

    The folder is imported as the package ``package`` (default: the folder's
    name), and the folder that holds that package is added to the front of
    ``sys.path``, as Python does for the folder of a script you run. So
    ``builders/`` is imported as ``builders`` (``builders.pd14``), and
    ``models/brian2/`` with ``package="models.brian2"``, which keeps it apart
    from the ``brian2`` package. Your project's files win over an installed
    package of the same name. With ``packages_only`` plain ``.py`` files are
    skipped. An error raised while importing propagates, so a broken module
    fails loudly instead of silently disappearing. A folder that does not
    exist gives ``{}``.
    """

    folder = Path(folder).resolve()
    if not folder.is_dir():
        return {}

    package = package or folder.name
    root = folder.parents[package.count(".")]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    modules: dict[str, ModuleType] = {}
    for module_info in pkgutil.iter_modules([str(folder)]):
        if packages_only and not module_info.ispkg:
            continue
        modules[module_info.name] = importlib.import_module(f"{package}.{module_info.name}")
    return modules


def find_definitions(
    folder: str | Path, package: str, module_names: Sequence[str], kinds: Sequence[type]
) -> dict[type, dict[str, Any]]:
    """
    The objects of each kind in ``kinds``, by their ``name``: every one at the
    top level of the files in ``folder`` (imported as ``package``) and of the
    modules ``module_names``.

    A config file names a definition (``model: iaf_psc_exp``); the backend
    looks it up here. A module that fails to import raises.

    Raises
    ------
    ValueError
        If two different objects of the same kind have the same name.
    """

    modules = list(import_folder_modules(folder, package=package).values())
    modules += [importlib.import_module(name) for name in module_names]

    found: dict[type, dict[str, Any]] = {kind: {} for kind in kinds}
    for module in modules:
        for item in vars(module).values():
            kind = next((kind for kind in kinds if isinstance(item, kind)), None)
            if kind is None:
                continue
            # The same object seen again, e.g. imported by another module.
            if found[kind].get(item.name, item) is not item:
                raise ValueError(
                    f"Two {kind.__name__} objects are named {item.name!r}; the second is in "
                    f"{module.__name__}."
                )
            found[kind][item.name] = item
    return found


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
