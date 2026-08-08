"""
Registry of bundled analysis diagnostics (raster, firing rates, ...).

Same registry pattern already used elsewhere in this package for
"pluggable, named thing" problems -- simulator backends
(microcircuit_lab.backends.get_backend), model generators
(microcircuit_lab.models.MODEL_GENERATORS), spectral estimators
(power_spectrum.POWER_SPECTRUM_METHODS). Applied to plots: adding a new
bundled diagnostic means writing its plot function + config class (the
actual work, same as today) plus one register_plot(...) call -- no
AnalysisConfig edits, no CLI hand-writing, no extra __init__.py exports
required for it to be usable through scripts/run_simulation.py.

Each of raster.py/firing_rates.py/power_spectrum.py/irregularity.py
calls register_plot() once at module level, so importing
microcircuit_lab.analysis (which already imports all four) populates
this registry as a side effect. A project's own custom diagnostic (e.g.
under experiments/<model>/) can call register_plot() the same way to
plug into the same generic CLI/YAML dispatch without editing this
package at all.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from microcircuit_lab.config.analysis import AnalysisConfig
from microcircuit_lab.config.base import FrozenConfig


@dataclass(frozen=True)
class PlotSpec:
    """One registered diagnostic: its config type, plot function, and the
    filename it's saved as under a run's plots/ directory.

    plot_fn must accept the common kwarg set every bundled plot function
    already does: (simulation, begin, end, area, style, config, save_path,
    show). Anything plot-specific belongs on config_cls, not as an extra
    argument here -- that's what keeps the dispatch in
    scripts/run_simulation.py generic.
    """

    config_cls: type[FrozenConfig]
    plot_fn: Callable[..., object]
    filename: str


PLOT_REGISTRY: dict[str, PlotSpec] = {}


def register_plot(
    name: str,
    *,
    config_cls: type[FrozenConfig],
    plot_fn: Callable[..., object],
    filename: str,
) -> None:
    """Register a diagnostic under `name` (the AnalysisConfig YAML
    section / --<name> CLI flag it's addressed by)."""

    PLOT_REGISTRY[name] = PlotSpec(config_cls=config_cls, plot_fn=plot_fn, filename=filename)


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
