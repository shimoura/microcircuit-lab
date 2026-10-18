"""What the config files may contain, checked with pydantic.

One module per YAML file of a network folder (``populations.py`` for
``populations.yaml``, ``stimuli.py`` for ``stimuli.yaml``, ...), plus
``network.py`` for the whole network, ``simulation.py`` and ``analysis.py``.
Import a model from the module that holds it
(``from microcircuit_lab.config.stimuli import PoissonStimulusConfig``); only
the most used ones are also available here.
"""

from .analysis import (
    AnalysisConfig,
    FiringRatePlotConfig,
    IsiCvPlotConfig,
    PlotStyle,
    PowerSpectrumPlotConfig,
    RasterPlotConfig,
)
from .network import NetworkConfig
from .simulation import SimulationConfig

__all__ = [
    "AnalysisConfig",
    "FiringRatePlotConfig",
    "IsiCvPlotConfig",
    "NetworkConfig",
    "PlotStyle",
    "PowerSpectrumPlotConfig",
    "RasterPlotConfig",
    "SimulationConfig",
]