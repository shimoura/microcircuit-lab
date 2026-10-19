"""Analysis and visualization utilities."""

from .areas import list_areas, select_populations
from .firing_rates import (
    cached_population_firing_rates,
    check_reference_rates,
    compute_neuron_firing_rates,
    compute_population_firing_rates,
    compute_reference_deviation,
    plot_firing_rates,
)
from .isi_cv import (
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
    population_color,
    population_label,
)
from .power_spectrum import (
    POWER_SPECTRUM_METHODS,
    cached_power_spectrum,
    compute_power_spectrum,
    plot_power_spectrum,
)
from .raster import plot_raster

# Imported after the four plot modules above: importing them registers
# their plots in PLOT_REGISTRY.
from .run_command_plots import (
    PLOT_REGISTRY,
    PlotSpec,
    call_plot,
    check_unknown_plot_sections,
    discover_plots,
    plot_enabled_in_config,
    register_plot,
)

__all__ = [
    "PLOT_REGISTRY",
    "list_areas",
    "FiringRatePlotConfig",
    "IsiCvPlotConfig",
    "POWER_SPECTRUM_METHODS",
    "PlotSpec",
    "PlotStyle",
    "PowerSpectrumPlotConfig",
    "RasterPlotConfig",
    "cached_population_firing_rates",
    "cached_power_spectrum",
    "call_plot",
    "check_reference_rates",
    "check_unknown_plot_sections",
    "compute_neuron_firing_rates",
    "compute_neuron_isi_cv",
    "compute_population_firing_rates",
    "compute_population_isi_cv",
    "compute_power_spectrum",
    "compute_reference_deviation",
    "discover_plots",
    "plot_firing_rates",
    "plot_isi_cv",
    "plot_power_spectrum",
    "plot_enabled_in_config",
    "plot_raster",
    "population_color",
    "population_label",
    "register_plot",
    "select_populations",
]
