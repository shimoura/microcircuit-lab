"""
Registry of analysis diagnostics: the bundled ones (raster, firing rates, ...)
and a project's own.

Same registry pattern already used elsewhere in this package for
"pluggable, named thing" problems -- simulator backends
(microcircuit_lab.backends.get_backend), model builders
(microcircuit_lab.io.discover_builders), spectral estimators
(power_spectrum.POWER_SPECTRUM_METHODS). Applied to plots: adding a new
bundled diagnostic means writing its plot function + config class (the
actual work, same as today) plus one register_plot(...) call -- no
AnalysisConfig edits, no CLI hand-writing, no extra __init__.py exports
required for it to be usable through microcircuit-lab run.

Each of raster.py/firing_rates.py/power_spectrum.py/irregularity.py
calls register_plot() once at module level, so importing
microcircuit_lab.analysis (which already imports all four) populates
this registry as a side effect.

A project's own diagnostics live outside this package and are found by
:func:`discover_plots`, which microcircuit-lab run calls before it
builds its command-line flags. It looks in two places:

* the ``analyses/`` folder of the project you run from -- every module or
  package in it is imported, and its register_plot() call runs on import;
* installed packages that list a module under the
  ``microcircuit_lab.analyses`` entry-point group in their
  ``pyproject.toml``::

      [project.entry-points."microcircuit_lab.analyses"]
      my_plots = "my_package.plots"

So a project adds a plot without editing this package at all.

PLOT_REGISTRY is shared state: it is filled as modules are imported, so
what it holds depends on which modules have been imported so far. Tests
that register plots work on a copy of it.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import entry_points
from pathlib import Path

from microcircuit_lab.config.analysis import AnalysisConfig
from microcircuit_lab.config.base import FrozenConfig
from microcircuit_lab.io.discovery import import_folder_modules

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
    Anything plot-specific belongs in that config, not as an extra argument
    -- that's what keeps the dispatch in microcircuit-lab run generic.
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
    """Register a diagnostic under `name` (the AnalysisConfig YAML
    section / --<name> CLI flag it's addressed by).

    plot_fn takes the simulation first, then any of PLOT_ARGUMENTS by name;
    a parameter with another name needs a default value. config_cls is
    optional: without it ``config`` is the plain dict from the plot's YAML
    section, and the plot is off unless that section sets ``enabled: true``
    or the flag is passed. With it, config_cls must have an ``enabled``
    field. filename defaults to ``<name>.png``. Raises if the name is
    already taken, so a project's plot cannot silently replace a bundled
    one.
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
    """Import the project's plot modules so their register_plot() calls run.

    Looks in ``analyses_dir`` and in the ``microcircuit_lab.analyses``
    entry-point group (see the module docstring). Nothing is returned: the
    plots end up in PLOT_REGISTRY. An error raised while importing a
    module propagates, so a broken plot fails loudly instead of silently
    disappearing.
    """

    import_folder_modules(analyses_dir)

    for entry_point in entry_points(group=PLOT_ENTRY_POINT_GROUP):
        entry_point.load()


def check_unknown_plot_sections(analysis_config: AnalysisConfig) -> None:
    """
    Raise if `analysis_config` has a top-level section that doesn't match
    any registered plot name.

    AnalysisConfig itself (microcircuit_lab.config, which has no
    dependency on matplotlib or this analysis package) accepts any extra
    top-level key without validation, so a typo'd YAML section (e.g.
    `rastr:` instead of `raster:`) would otherwise be silently ignored
    instead of raising. Call this once after loading an AnalysisConfig,
    before using it to drive plots.
    """

    unknown = set(analysis_config.model_extra or {}) - set(PLOT_REGISTRY)
    if unknown:
        raise ValueError(
            f"Unknown analysis plot section(s): {sorted(unknown)}. "
            f"Registered plots: {sorted(PLOT_REGISTRY)}. A custom plot must "
            "be registered (microcircuit_lab.analysis.register_plot) before "
            "its YAML section is recognized."
        )
