"""
Analysis/plot configuration models.

This module defines immutable configuration objects describing how
analysis plots (raster, firing rates, power spectrum, ISI CV) should be
selected and presented. Mirrors the network/simulation config pattern:
pydantic models, validated, loadable from YAML.

No plotting/matplotlib code belongs here -- see
microcircuit_lab.analysis.plot_styles for the functions that consume
these models.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import ConfigDict, Field

from microcircuit_lab.config.base import FrozenConfig

ColorMode = Literal["layer", "cell_type", "population", "custom"]


# -----------------------------------------------------------------------------
# Style
# -----------------------------------------------------------------------------
class PlotStyle(FrozenConfig):
    """Shared visual settings used across analysis plots."""

    color_mode: ColorMode = "layer"
    layer_colors: dict[str, str] = Field(default_factory=lambda: {
        "L23": "tab:blue", "L4": "tab:orange", "L5": "tab:green", "L6": "tab:red",
    })
    cell_type_colors: dict[str, str] = Field(
        default_factory=lambda: {"E": "tab:blue", "I": "tab:red"}
    )
    custom_colors: dict[str, str] = Field(default_factory=dict)
    excitatory_tone: float = 0.25
    inhibitory_tone: float = 0.65
    population_labels: dict[str, str] = Field(default_factory=dict)
    tick_label_size: float = 8.0
    axis_label_size: float = 9.0
    title_size: float = 10.0
    legend_size: float = 8.0
    dpi: int = 300


# -----------------------------------------------------------------------------
# Per-plot presentation settings
# -----------------------------------------------------------------------------
class RasterPlotConfig(FrozenConfig):
    """Raster-specific presentation settings."""

    enabled: bool = True
    marker_size: float = 1.0
    alpha: float = 0.8
    figsize: tuple[float, float] | None = None
    width: float = 10.0
    height_per_population: float = 0.55
    min_height: float = 4.0
    separator_lines: bool = True
    separator_alpha: float = 0.25
    show_legend: bool = True
    invert_yaxis: bool = True
    max_neurons_per_population: int | None = Field(default=None, gt=0)
    neuron_fraction: float | None = Field(default=None, gt=0.0, le=1.0)
    begin: float | None = Field(default=None, ge=0.0)
    end: float | None = Field(default=None, ge=0.0)


class FiringRatePlotConfig(FrozenConfig):
    """Firing-rate distribution presentation settings."""

    enabled: bool = True
    figsize: tuple[float, float] | None = None
    width: float = 8.0
    height_per_population: float = 0.55
    min_height: float = 3.5
    violin_alpha: float = 0.35
    box_width: float = 0.18
    show_points: bool = False
    max_points_per_population: int = 500
    point_size: float = 8.0
    point_alpha: float = 0.2
    show_mean: bool = True
    mean_marker_size: float = 28.0
    show_legend: bool = True
    invert_yaxis: bool = True
    show_reference: bool = False


class IsiCvPlotConfig(FiringRatePlotConfig):
    """ISI-CV distribution presentation settings.

    Same layout as FiringRatePlotConfig (per-population violin/box plot),
    plus the minimum spike count required for a neuron's CV to be defined.
    """

    min_spikes: int = Field(default=3, ge=2)


class PowerSpectrumPlotConfig(FrozenConfig):
    """Power-spectrum presentation settings (grid: one subplot per population,
    grouped into rows by layer -- see analysis.power_spectrum._grid_layout).

    method_kwargs are forwarded to the chosen estimator (see
    analysis.power_spectrum.POWER_SPECTRUM_METHODS), e.g. {"bandwidth": 4.0}
    for method="multitaper".
    """

    enabled: bool = True
    method: str = "welch"
    method_kwargs: dict = Field(default_factory=dict)
    figsize: tuple[float, float] | None = None
    width_per_column: float = 3.0
    height_per_row: float = 1.8
    min_width: float = 4.5
    min_height: float = 2.2
    linewidth: float = 1.2
    log_power: bool = False
    log_freq: bool = False
    xlim: tuple[float, float] | None = None


# -----------------------------------------------------------------------------
# Analysis
# -----------------------------------------------------------------------------
class AnalysisConfig(FrozenConfig):
    """
    Complete analysis/plotting configuration.

    ``begin``/``end``/``area``/``show_reference``/``style`` are the only
    fixed fields -- true cross-plot defaults, shared by every diagnostic.
    Everything else is open-ended: any other top-level key (``raster``,
    ``firing_rates``, ``power_spectrum``, ``isi_cv``, or a plot your own
    code registers -- see ``microcircuit_lab.analysis.registry``) is kept
    as-is and resolved on demand through :meth:`plot_config`. This is
    what lets a new diagnostic be added without ever touching this class:
    its YAML section just needs a name, not a pre-declared field.

    Contains no biological network or execution parameters -- those
    belong to NetworkConfig/SimulationConfig respectively.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    begin: float = Field(default=0.0, ge=0.0)
    end: float | None = None
    area: str | None = None
    show_reference: bool = False

    style: PlotStyle = PlotStyle()

    def plot_config(
        self, name: str, config_cls: type[FrozenConfig] | None
    ) -> FrozenConfig | dict:
        """
        Validate this config's ``name`` section (or ``{}`` if absent)
        against ``config_cls`` -- how a specific plot's own settings are
        pulled out of the open-ended extra fields above. Without a
        ``config_cls`` the section is returned as a plain dict.
        """

        raw = (self.model_extra or {}).get(name, {})
        if config_cls is None:
            return dict(raw)
        return config_cls.model_validate(raw)

    @classmethod
    def from_yaml(
        cls,
        config_dir: str | Path = "configs",
        network_name: str = "toy",
        analysis_name: str | None = None,
    ) -> "AnalysisConfig":
        """
        Build an AnalysisConfig from ``configs/analysis/<analysis_name or
        network_name>.yaml``.

        ``analysis_name`` defaults to ``network_name`` when omitted, same
        convention as ``Simulation.from_yaml``'s ``simulation_name``. If
        the file doesn't exist, all-defaults ``AnalysisConfig()`` is
        returned instead of raising -- a network without a custom
        analysis profile just gets the generic presentation.
        """

        # Deferred: microcircuit_lab.io eagerly pulls in backends/network,
        # which import this module's package (microcircuit_lab.config)
        # while it's still initializing -- a module-level import here
        # would be circular.
        from microcircuit_lab.io.files import read_yaml

        analysis_name = network_name if analysis_name is None else analysis_name
        path = Path(config_dir) / "analysis" / f"{analysis_name}.yaml"
        if not path.exists():
            return cls()
        return cls.model_validate(read_yaml(path))
