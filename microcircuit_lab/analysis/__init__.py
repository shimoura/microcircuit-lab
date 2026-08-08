"""Analysis and visualization utilities."""

from .firing_rates import (
    check_reference_rates,
    compute_neuron_firing_rates,
    compute_population_firing_rates,
    compute_reference_deviation,
    plot_firing_rates,
)
from .irregularity import (
    compute_neuron_isi_cv,
    compute_population_isi_cv,
    plot_isi_cv,
)
from .plot_styles import (
    FiringRatePlotConfig,
    IsiCvPlotConfig,
    PlotStyle,
    PowerSpectrumPlotConfig,
    RasterPlotConfig,
)
from .power_spectrum import (
    POWER_SPECTRUM_METHODS,
    compute_power_spectrum,
    plot_power_spectrum,
)
from .raster import plot_raster

# Imported after the four plot modules above, whose module-level
# register_plot(...) calls populate PLOT_REGISTRY as a side effect of
# the imports already happening here.
from .registry import PLOT_REGISTRY, PlotSpec, check_unknown_plot_sections, register_plot

__all__ = [
    "PLOT_REGISTRY",
    "FiringRatePlotConfig",
    "IsiCvPlotConfig",
    "POWER_SPECTRUM_METHODS",
    "PlotSpec",
    "PlotStyle",
    "PowerSpectrumPlotConfig",
    "RasterPlotConfig",
    "check_reference_rates",
    "check_unknown_plot_sections",
    "compute_neuron_firing_rates",
    "compute_neuron_isi_cv",
    "compute_population_firing_rates",
    "compute_population_isi_cv",
    "compute_power_spectrum",
    "compute_reference_deviation",
    "plot_firing_rates",
    "plot_isi_cv",
    "plot_power_spectrum",
    "plot_raster",
    "register_plot",
]
