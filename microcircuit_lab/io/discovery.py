"""
Import the modules of a project folder (``builders/``, ``analyses/``).

Shared by :func:`~microcircuit_lab.io.builders.discover_builders` and
:func:`~microcircuit_lab.analysis.registry.discover_plots`, which both look
in a folder of the project you run from.
"""

from __future__ import annotations

import importlib
import pkgutil
import sys
from pathlib import Path
from types import ModuleType


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
