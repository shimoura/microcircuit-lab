"""docs/config_files.md and its picture are written from the config models and must be up to date."""

import importlib.util
from pathlib import Path

from microcircuit_lab.analysis.run_command_plots import PlotSpec
from microcircuit_lab.config.analysis import RasterPlotConfig

SCRIPT = Path(__file__).resolve().parents[1] / "docs" / "write_config_files.py"
spec = importlib.util.spec_from_file_location("write_config_files", SCRIPT)
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


def test_the_page_is_up_to_date():
    # render() also stops on a field without a description or an invalid example.
    assert reference.PAGE.read_text(encoding="utf-8") == reference.render(), (
        "docs/config_files.md is out of date: run python docs/write_config_files.py"
    )
    assert reference.IMAGE.read_text(encoding="utf-8") == reference.names_svg(), (
        "docs/images/config_names.svg is out of date: run python docs/write_config_files.py"
    )


def test_a_project_plot_is_not_on_the_page(monkeypatch):
    # A project's plots are registered by discover_plots, with or without a config class.
    def plot(run):
        pass

    before = reference.render()
    monkeypatch.setitem(reference.PLOT_REGISTRY, "no_class", PlotSpec(plot_fn=plot, filename="a.png"))
    monkeypatch.setitem(
        reference.PLOT_REGISTRY, "with_class", PlotSpec(plot_fn=plot, filename="b.png", config_cls=RasterPlotConfig)
    )
    assert reference.render() == before
