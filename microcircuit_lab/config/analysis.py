"""What the analysis file may contain: which plots to make and how they look."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from pydantic import ConfigDict, Field

from microcircuit_lab.config.frozen_config import FrozenConfig
from microcircuit_lab.config.yaml_files import read_yaml

ColorMode = Literal["layer", "cell_type", "population", "custom"]

logger = logging.getLogger(__name__)


class PlotStyle(FrozenConfig):
    """Shared visual settings used across analysis plots."""

    color_mode: ColorMode = Field(
        default="layer",
        description="layer: a color per layer, mixed with white by excitatory_tone (E) or "
        "inhibitory_tone (I); cell_type: a color per cell type; population: matplotlib's "
        "color cycle; custom: custom_colors",
    )
    layer_colors: dict[str, str] = Field(
        default_factory=lambda: {
            "L23": "tab:blue", "L4": "tab:orange", "L5": "tab:green", "L6": "tab:red",
        },
        description="color per layer, for color_mode: layer",
    )
    cell_type_colors: dict[str, str] = Field(
        default_factory=lambda: {"E": "tab:blue", "I": "tab:red"},
        description="color per cell type, for color_mode: cell_type",
    )
    custom_colors: dict[str, str] = Field(
        default_factory=dict,
        examples=[{"E": "#595289", "I": "#af143c"}],
        description="color per population name, for color_mode: custom",
    )
    excitatory_tone: float = Field(
        default=0.25, description="for color_mode: layer, how much white is mixed into E colors (0-1)"
    )
    inhibitory_tone: float = Field(
        default=0.65, description="for color_mode: layer, how much white is mixed into I colors (0-1)"
    )
    population_labels: dict[str, str] = Field(
        default_factory=dict,
        examples=[{"L23_E": "L2/3E"}],
        description="label to show instead of a population name",
    )
    tick_label_size: float = Field(default=8.0, description="font size of tick labels (pt)")
    axis_label_size: float = Field(default=9.0, description="font size of axis labels (pt)")
    title_size: float = Field(default=10.0, description="font size of titles (pt)")
    legend_size: float = Field(default=8.0, description="font size of legends (pt)")
    dpi: int = Field(default=300, description="resolution of the saved figures")


class RasterPlotConfig(FrozenConfig):
    """Raster-specific presentation settings."""

    enabled: bool = Field(default=True, description="make this plot")
    marker_size: float = Field(default=1.5, description="size of a spike dot")
    alpha: float = Field(default=0.8, description="opacity of the dots (0-1)")
    figsize: tuple[float, float] | None = Field(
        default=None,
        examples=[[6.0, 4.0]],
        description="width and height (inches); omit to size from the number of populations",
    )
    width: float = Field(default=6.0, description="width (inches) when figsize is omitted")
    height_per_population: float = Field(
        default=0.55, description="height per population (inches) when figsize is omitted"
    )
    min_height: float = Field(default=4.0, description="smallest height (inches) when figsize is omitted")
    separator_lines: bool = Field(default=True, description="draw a line between populations")
    separator_alpha: float = Field(default=0.25, description="opacity of those lines (0-1)")
    show_legend: bool = Field(default=False, description="show a legend (the populations are also named on the y axis)")
    invert_yaxis: bool = Field(default=True, description="first population at the top")
    max_neurons_per_population: int | None = Field(
        default=None, gt=0, description="show at most this many neurons per population; omit for all"
    )
    neuron_fraction: float | None = Field(
        default=None,
        gt=0.0,
        le=1.0,
        examples=[0.05],
        description="show this fraction of each population's neurons; replaces "
        "max_neurons_per_population when set",
    )
    begin: float | None = Field(
        default=None, ge=0.0, description="start of this plot only (ms); omit to use the top-level begin"
    )
    end: float | None = Field(
        default=None, ge=0.0, description="end of this plot only (ms); omit to use the top-level end"
    )


class _DistributionPlotConfig(FrozenConfig):
    """Settings shared by the per-population distribution plots (violin and box)."""

    enabled: bool = Field(default=True, description="make this plot")
    figsize: tuple[float, float] | None = Field(
        default=None,
        examples=[[6.0, 4.0]],
        description="width and height (inches); omit to size from the number of populations",
    )
    width: float = Field(default=8.0, description="width (inches) when figsize is omitted")
    height_per_population: float = Field(
        default=0.55, description="height per population (inches) when figsize is omitted"
    )
    min_height: float = Field(default=3.5, description="smallest height (inches) when figsize is omitted")
    violin_alpha: float = Field(default=0.35, description="opacity of the violins (0-1)")
    box_width: float = Field(default=0.18, description="width of the boxes")
    show_mean: bool = Field(default=True, description="mark each population's mean")
    mean_marker_size: float = Field(default=28.0, description="size of that mark")
    invert_yaxis: bool = Field(default=True, description="first population at the top")


class FiringRatePlotConfig(_DistributionPlotConfig):
    """Firing-rate distribution presentation settings."""

    show_points: bool = Field(default=False, description="also show each neuron's rate as a dot")
    max_points_per_population: int = Field(
        default=500, description="at most this many dots per population (picked at random)"
    )
    point_size: float = Field(default=8.0, description="size of a dot")
    point_alpha: float = Field(default=0.2, description="opacity of the dots (0-1)")
    show_legend: bool = Field(default=True, description="show a legend")


class IsiCvPlotConfig(_DistributionPlotConfig):
    """ISI-CV distribution presentation settings: the layout of the firing-rate
    plot, plus the minimum spike count for a neuron's CV to be defined."""

    min_spikes: int = Field(
        default=3, ge=2, description="neurons with fewer spikes in the window are left out"
    )


class PowerSpectrumPlotConfig(FrozenConfig):
    """Power-spectrum settings: one subplot per population, in rows by layer.

    ``method_kwargs`` are passed to the chosen method (see
    ``analysis.power_spectrum.POWER_SPECTRUM_METHODS``), for example
    ``{"bandwidth": 4.0}`` for ``method="multitaper"``.
    """

    enabled: bool = Field(default=True, description="make this plot")
    method: str = Field(default="welch", description="welch, periodogram or multitaper")
    method_kwargs: dict = Field(
        default_factory=dict,
        examples=[{"bandwidth": 4.0}],
        description="passed to the method, e.g. bandwidth for multitaper",
    )
    figsize: tuple[float, float] | None = Field(
        default=None,
        examples=[[9.0, 6.0]],
        description="width and height (inches); omit to size from the grid",
    )
    width_per_column: float = Field(default=3.0, description="width per column (inches) when figsize is omitted")
    height_per_row: float = Field(default=1.8, description="height per row (inches) when figsize is omitted")
    min_width: float = Field(default=4.5, description="smallest width (inches) when figsize is omitted")
    min_height: float = Field(default=2.2, description="smallest height (inches) when figsize is omitted")
    linewidth: float = Field(default=1.2, description="line width")
    log_power: bool = Field(default=False, description="power on a log axis")
    log_freq: bool = Field(default=False, description="frequency on a log axis")
    xlim: tuple[float, float] | None = Field(
        default=None,
        examples=[[1.0, 150.0]],
        description="frequency range to show (Hz); omit for all; with log_freq, start above 0",
    )


class AnalysisConfig(FrozenConfig):
    """
    The analysis file: settings shared by all plots, plus one section per plot.

    ``begin``, ``end``, ``area``, ``show_reference`` and ``style`` are the only
    fixed fields. Any other top-level key (``raster``, ``firing_rates``,
    ``power_spectrum``, ``isi_cv``, or a plot you register yourself, see
    ``microcircuit_lab.analysis.run_command_plots``) is kept as written and read with
    :meth:`plot_config`. So a new plot needs no change to this class.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    begin: float = Field(
        default=0.0, ge=0.0, description="start of the analysed time (ms), e.g. after the transient"
    )
    end: float | None = Field(
        default=None, examples=[1000.0], description="end of the analysed time (ms); omit for the end of the run"
    )
    area: str | None = Field(
        default=None,
        examples=["all"],
        description="multi-area networks: one area's name, or all for one set of plots per "
        "area; omit to plot every population together",
    )
    show_reference: bool = Field(
        default=False, description="mark the reference rates on the firing-rate plot (as --reference)"
    )

    style: PlotStyle = Field(default=PlotStyle(), description="colors, labels and sizes of every plot")

    def plot_config(
        self, name: str, config_cls: type[FrozenConfig] | None
    ) -> FrozenConfig | dict:
        """
        Read the ``name`` section (``{}`` if absent) as a ``config_cls``.
        Without a ``config_cls`` the section is returned as a plain dict.
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
    ) -> AnalysisConfig:
        """
        Read ``configs/analysis/<analysis_name>.yaml``.

        ``analysis_name`` defaults to ``network_name``, as ``simulation_name``
        does in ``Simulation.from_yaml``. If that default file doesn't exist, the
        defaults of ``AnalysisConfig()`` are used, with a warning; a file named
        explicitly must exist.
        """

        name_is_explicit = analysis_name is not None
        analysis_name = network_name if analysis_name is None else analysis_name
        path = Path(config_dir) / "analysis" / f"{analysis_name}.yaml"
        if path.exists():
            return cls.model_validate(read_yaml(path))
        if name_is_explicit:
            raise FileNotFoundError(f"No analysis file at {path}.")
        logger.warning("No analysis file at %s; using the default plot settings.", path)
        return cls()
