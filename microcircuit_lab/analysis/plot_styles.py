"""Reusable plotting configuration for simulation analyses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ColorMode = Literal["layer", "cell_type", "population", "custom"]


@dataclass(frozen=True)
class RasterPlotConfig:
    """Presentation settings for spike raster plots.

    Data selection (area/populations/time window) is intentionally kept in
    ``plot_raster``; this object only controls presentation.
    """

    color_mode: ColorMode = "layer"
    layer_colors: dict[str, str] = field(
        default_factory=lambda: {
            "L23": "tab:blue",
            "L4": "tab:orange",
            "L5": "tab:green",
            "L6": "tab:red",
        }
    )
    cell_type_colors: dict[str, str] = field(
        default_factory=lambda: {
            "E": "tab:blue",
            "I": "tab:red",
        }
    )
    custom_colors: dict[str, str] = field(default_factory=dict)
    excitatory_tone: float = 0.25
    inhibitory_tone: float = 0.65
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
    dpi: int = 300
    tick_label_size: float = 5.0
    axis_label_size: float = 8.0
    population_labels: dict[str, str] = field(default_factory=dict)


DEFAULT_RASTER_STYLE = RasterPlotConfig()
