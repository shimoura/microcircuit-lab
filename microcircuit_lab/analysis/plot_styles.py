"""Shared plotting styles for simulation analyses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import matplotlib.colors as mcolors
import numpy as np

ColorMode = Literal["layer", "cell_type", "population", "custom"]


@dataclass(frozen=True)
class PlotStyle:
    """Shared visual settings used across analysis plots."""

    color_mode: ColorMode = "layer"
    layer_colors: dict[str, str] = field(default_factory=lambda: {
        "L23": "tab:blue", "L4": "tab:orange", "L5": "tab:green", "L6": "tab:red",
    })
    cell_type_colors: dict[str, str] = field(default_factory=lambda: {"E": "tab:blue", "I": "tab:red"})
    custom_colors: dict[str, str] = field(default_factory=dict)
    excitatory_tone: float = 0.25
    inhibitory_tone: float = 0.65
    population_labels: dict[str, str] = field(default_factory=dict)
    tick_label_size: float = 8.0
    axis_label_size: float = 9.0
    title_size: float = 10.0
    legend_size: float = 8.0
    dpi: int = 300


@dataclass(frozen=True)
class RasterPlotConfig:
    """Raster-specific presentation settings."""

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


@dataclass(frozen=True)
class FiringRatePlotConfig:
    """Firing-rate distribution presentation settings."""

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


DEFAULT_PLOT_STYLE = PlotStyle()
DEFAULT_RASTER_CONFIG = RasterPlotConfig()
DEFAULT_FIRING_RATE_CONFIG = FiringRatePlotConfig()


def population_metadata(name: str) -> tuple[str | None, str | None, str | None]:
    """Infer area, layer, and E/I type from conventional population names."""
    import re

    area, local_name = (name.split("__", 1) + [None])[:2] if "__" in name else (None, name)
    match = re.search(r"(?:^|_)(L(?:23|[1-6]))_([EI])(?:$|_)", local_name)
    if match:
        return area, match.group(1), match.group(2)
    cell_match = re.search(r"(?:^|_)([EI])(?:$|_)", local_name)
    return area, None, cell_match.group(1) if cell_match else None


def population_color(name: str, index: int, style: PlotStyle) -> str | tuple[float, float, float]:
    """Resolve a consistent color for a population across analysis plots."""
    _, layer, cell_type = population_metadata(name)
    local_name = name.split("__", 1)[-1]

    if style.color_mode == "custom":
        return style.custom_colors.get(name, style.custom_colors.get(local_name, f"C{index % 10}"))
    if style.color_mode == "cell_type":
        return style.cell_type_colors.get(cell_type, f"C{index % 10}")
    if style.color_mode == "population":
        return f"C{index % 10}"

    base = style.layer_colors.get(layer, f"C{index % 10}")
    if cell_type not in {"E", "I"}:
        return base
    amount = style.excitatory_tone if cell_type == "E" else style.inhibitory_tone
    rgb = np.asarray(mcolors.to_rgb(base))
    return tuple(rgb + (1.0 - rgb) * amount)


def population_label(name: str, style: PlotStyle, *, strip_area: bool = False) -> str:
    """Resolve a display label for a population."""
    local_name = name.split("__", 1)[-1] if strip_area else name
    return style.population_labels.get(local_name, local_name)
