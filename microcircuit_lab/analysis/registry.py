"""
Registry of analysis plots: the bundled ones (raster, firing rates, ...) and a
project's own.

Adding a plot means writing its plot function and config class and calling
``register_plot`` once. Each bundled plot module does this at import, so
importing ``microcircuit_lab.analysis`` fills ``PLOT_REGISTRY``.

A project's own plots live outside this package. :func:`discover_plots`, which
``microcircuit-lab run`` calls before it builds its command-line flags, finds
them in two places:

* the ``analyses/`` folder of the project you run from: every module or
  package in it is imported, and its ``register_plot`` call runs on import;
* installed packages that list a module under the
  ``microcircuit_lab.analyses`` entry-point group in their
  ``pyproject.toml``::

      [project.entry-points."microcircuit_lab.analyses"]
      my_plots = "my_package.plots"

``PLOT_REGISTRY`` is filled as modules are imported, so what it holds depends
on what has been imported so far. Tests that register plots work on a copy.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import entry_points
from pathlib import Path

from microcircuit_lab.config.analysis import AnalysisConfig
from microcircuit_lab.config.base import FrozenConfig
from microcircuit_lab.discovery import import_folder_modules

#: Marks an argument that was not passed, so the plot falls back to its config.
#: An explicit None is a real value (``xlim=None`` means the full range).
UNSET = object()

PLOT_ENTRY_POINT_GROUP = "microcircuit_lab.analyses"


#: What microcircuit-lab run can hand to a plot function, by parameter
#: name. A function asks only for the ones it needs.
PLOT_ARGUMENTS = (
    "begin",
    "end",
    "area",
    "style",
    "config",
    "save_path",
    "show",
    "show_reference",
)


@dataclass(frozen=True)
class PlotSpec:
    """One registered diagnostic: its plot function, its optional config
    type, and the filename it's saved as under a run's plots/ directory.

    The first parameter of plot_fn is the simulation. Every other parameter
    it names from PLOT_ARGUMENTS is filled in by call_plot; a plot function
    asks only for what it needs. ``area`` is one area name or None
    (``--area all`` calls the function once per area), and the plot is
    saved to ``save_path``. ``config`` is an instance of config_cls, or
    the plain dict from the plot's YAML section when config_cls is None.
    Anything plot-specific belongs in that config, not as an extra argument,
    so that ``microcircuit-lab run`` can call every plot the same way.
    """

    plot_fn: Callable[..., object]
    filename: str
    config_cls: type[FrozenConfig] | None = None


PLOT_REGISTRY: dict[str, PlotSpec] = {}


def _extra_parameters(plot_fn: Callable[..., object]) -> list[inspect.Parameter]:
    """The parameters of plot_fn after the first one (the simulation)."""
    return list(inspect.signature(plot_fn).parameters.values())[1:]


def _check_plot_function(name: str, plot_fn: Callable[..., object]) -> None:
    """Raise if plot_fn asks for something microcircuit-lab run cannot provide."""

    if not inspect.signature(plot_fn).parameters:
        raise ValueError(f"Plot {name!r}: {plot_fn.__name__}() needs a first parameter for the simulation.")

    unknown = [
        parameter.name
        for parameter in _extra_parameters(plot_fn)
        if parameter.kind in (parameter.POSITIONAL_OR_KEYWORD, parameter.KEYWORD_ONLY)
        and parameter.default is parameter.empty
        and parameter.name not in PLOT_ARGUMENTS
    ]
    if unknown:
        raise ValueError(
            f"Plot {name!r}: {plot_fn.__name__}() asks for {unknown}, which "
            f"microcircuit-lab run cannot provide. After the simulation, a parameter can be "
            f"one of {list(PLOT_ARGUMENTS)}; give any other parameter a default value."
        )


def register_plot(
    name: str,
    plot_fn: Callable[..., object],
    *,
    config_cls: type[FrozenConfig] | None = None,
    filename: str | None = None,
) -> None:
    """
    Add a plot to ``microcircuit-lab run``.

    Parameters
    ----------
    name
        The plot's name: its ``--<name>`` flag and its section in the analysis
        file.
    plot_fn
        The plot function. It takes the simulation first, then any of
        ``PLOT_ARGUMENTS`` by name (``save_path``, ``area``, ``begin``, ...); a
        parameter with any other name needs a default value.
    config_cls
        Optional pydantic model for the plot's settings, with an ``enabled``
        field. Without it, ``config`` is the plain dict from the plot's section,
        and the plot is off unless that section sets ``enabled: true`` or the
        flag is passed.
    filename
        The figure's file name; ``<name>.png`` by default.

    Raises
    ------
    ValueError
        If the name is already taken, so a project's plot can't replace a
        bundled one, or if ``plot_fn`` asks for a parameter it can't be given.
    """

    if name in PLOT_REGISTRY:
        raise ValueError(f"A plot named {name!r} is already registered.")
    if config_cls is not None and "enabled" not in config_cls.model_fields:
        raise ValueError(f"{config_cls.__name__} needs an 'enabled' field to be used as a plot config.")

    _check_plot_function(name, plot_fn)

    PLOT_REGISTRY[name] = PlotSpec(
        plot_fn=plot_fn, filename=filename or f"{name}.png", config_cls=config_cls
    )


def call_plot(spec: PlotSpec, simulation, **available: object) -> object:
    """Call spec.plot_fn with the simulation and the values in `available`
    that it names as parameters."""

    wanted = {
        parameter.name: available[parameter.name]
        for parameter in _extra_parameters(spec.plot_fn)
        if parameter.name in available
    }
    return spec.plot_fn(simulation, **wanted)


def plot_enabled_in_config(plot_config: FrozenConfig | dict) -> bool:
    """Whether a plot's own settings switch it on: its ``enabled`` field, or
    for a plain-dict section the ``enabled`` key (off if absent)."""

    if isinstance(plot_config, dict):
        return plot_config.get("enabled", False)
    return plot_config.enabled


def discover_plots(analyses_dir: str | Path = "analyses") -> None:
    """
    Import the plots of the project you run from, so their ``register_plot``
    calls run.

    Looks in ``analyses_dir`` and in the ``microcircuit_lab.analyses``
    entry-point group. The plots end up in ``PLOT_REGISTRY``. An error in a
    module is raised, so a broken plot fails loudly instead of disappearing.

    Parameters
    ----------
    analyses_dir
        The project's analyses folder; a missing folder is fine.
    """

    import_folder_modules(analyses_dir)

    for entry_point in entry_points(group=PLOT_ENTRY_POINT_GROUP):
        entry_point.load()


def check_unknown_plot_sections(analysis_config: AnalysisConfig) -> None:
    """
    Raise if `analysis_config` has a top-level section that doesn't match
    any registered plot name.

    ``AnalysisConfig`` accepts any extra top-level key, so a misspelled
    section (``rastr:`` instead of ``raster:``) would otherwise be ignored
    silently. Call this once after loading an ``AnalysisConfig``, before
    using it to draw plots.
    """

    unknown = set(analysis_config.model_extra or {}) - set(PLOT_REGISTRY)
    if unknown:
        raise ValueError(
            f"Unknown analysis plot section(s): {sorted(unknown)}. "
            f"Registered plots: {sorted(PLOT_REGISTRY)}. A custom plot must "
            "be registered (microcircuit_lab.analysis.register_plot) before "
            "its YAML section is recognized."
        )
