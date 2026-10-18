"""Shared plotting styles for simulation analyses."""

from __future__ import annotations

import matplotlib.colors as mcolors
import numpy as np

from microcircuit_lab.config.analysis import (
    ColorMode,
    FiringRatePlotConfig,
    IsiCvPlotConfig,
    PlotStyle,
    PowerSpectrumPlotConfig,
    RasterPlotConfig,
)

__all__ = [
    "ColorMode",
    "FiringRatePlotConfig",
    "IsiCvPlotConfig",
    "PlotStyle",
    "PowerSpectrumPlotConfig",
    "RasterPlotConfig",
    "DEFAULT_PLOT_STYLE",
    "DEFAULT_RASTER_CONFIG",
    "DEFAULT_FIRING_RATE_CONFIG",
    "DEFAULT_POWER_SPECTRUM_CONFIG",
    "DEFAULT_ISI_CV_CONFIG",
    "population_metadata",
    "population_color",
    "population_label",
]

DEFAULT_PLOT_STYLE = PlotStyle()
DEFAULT_RASTER_CONFIG = RasterPlotConfig()
DEFAULT_FIRING_RATE_CONFIG = FiringRatePlotConfig()
DEFAULT_POWER_SPECTRUM_CONFIG = PowerSpectrumPlotConfig()
DEFAULT_ISI_CV_CONFIG = IsiCvPlotConfig()


def population_metadata(name: str) -> tuple[str | None, str | None, str | None]:
    """Infer area, layer, and cell type from conventional population names.

    ``<area>__L<layer>_<type>`` gives all three, e.g. ``B__L23_VIP`` gives
    ``("B", "L23", "VIP")``; the type is any name (``E``, ``I``, ``PV``, ...),
    up to the next underscore. Without a layer only a plain ``E``/``I`` is
    recognised as a type.
    """
    import re

    area, local_name = (name.split("__", 1) + [None])[:2] if "__" in name else (None, name)
    match = re.search(r"(?:^|_)(L(?:23|[1-6]))_([A-Za-z0-9]+)", local_name)
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
