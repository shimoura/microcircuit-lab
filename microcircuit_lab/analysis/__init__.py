"""Analysis and visualization utilities."""

from .firing_rates import (
    compute_neuron_firing_rates,
    compute_population_firing_rates,
    plot_firing_rates,
)
from .plot_styles import FiringRatePlotConfig, PlotStyle, RasterPlotConfig
from .raster import plot_raster

__all__ = [
    "FiringRatePlotConfig",
    "PlotStyle",
    "RasterPlotConfig",
    "compute_neuron_firing_rates",
    "compute_population_firing_rates",
    "plot_firing_rates",
    "plot_raster",
]
