"""Discovery of a project's own plots (analyses/ folder and entry points).
Uses throwaway plot modules written to a temporary folder, so the tests do
not depend on which plots are bundled."""

import sys
from importlib.metadata import EntryPoint
from pathlib import Path

import pytest

from microcircuit_lab.analysis import call_plot, discover_plots, register_plot
from microcircuit_lab.analysis import registry as registry_module
from microcircuit_lab.config.base import FrozenConfig

PLOT_MODULE = """\
from microcircuit_lab.analysis import register_plot


def plot(simulation, save_path):
    pass


register_plot("{name}", plot)
"""


@pytest.fixture(autouse=True)
def isolated_registry_and_imports(monkeypatch):
    """Give each test its own registry copy, and forget modules and
    sys.path entries the test imported from its temporary folder."""
    monkeypatch.setattr(registry_module, "PLOT_REGISTRY", dict(registry_module.PLOT_REGISTRY))
    monkeypatch.setattr(sys, "path", list(sys.path))
    modules_before = set(sys.modules)
    yield
    for name in set(sys.modules) - modules_before:
        del sys.modules[name]


def _write_plot(folder: Path, module: str, plot_name: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{module}.py").write_text(PLOT_MODULE.format(name=plot_name))


def test_a_module_in_the_folder_registers_its_plot(tmp_path: Path) -> None:
    _write_plot(tmp_path / "plots_a", "rate_bars", "rate_bars_a")

    discover_plots(tmp_path / "plots_a")

    assert registry_module.PLOT_REGISTRY["rate_bars_a"].filename == "rate_bars_a.png"


def test_a_missing_folder_adds_no_plots(tmp_path: Path) -> None:
    before = dict(registry_module.PLOT_REGISTRY)

    discover_plots(tmp_path / "no_such_folder")

    assert registry_module.PLOT_REGISTRY == before


def test_a_module_that_fails_to_import_raises(tmp_path: Path) -> None:
    folder = tmp_path / "plots_b"
    folder.mkdir()
    (folder / "broken.py").write_text("raise RuntimeError('broken plot')\n")

    with pytest.raises(RuntimeError, match="broken plot"):
        discover_plots(folder)


def test_an_installed_package_can_register_plots(monkeypatch, tmp_path: Path) -> None:
    _write_plot(tmp_path / "site", "external_plots", "external_plot")
    monkeypatch.syspath_prepend(str(tmp_path / "site"))
    external = EntryPoint(
        name="external", value="external_plots", group=registry_module.PLOT_ENTRY_POINT_GROUP
    )
    monkeypatch.setattr(registry_module, "entry_points", lambda group: [external])

    discover_plots(tmp_path / "no_such_folder")

    assert "external_plot" in registry_module.PLOT_REGISTRY


class _Config(FrozenConfig):
    enabled: bool = False


def _plot(simulation, **kwargs) -> None:
    pass


def test_registering_a_name_twice_raises() -> None:
    register_plot("twice", config_cls=_Config, plot_fn=_plot, filename="twice.png")

    with pytest.raises(ValueError, match="already registered"):
        register_plot("twice", config_cls=_Config, plot_fn=_plot, filename="twice.png")


def test_a_plot_cannot_replace_a_bundled_one() -> None:
    with pytest.raises(ValueError, match="already registered"):
        register_plot("raster", config_cls=_Config, plot_fn=_plot, filename="raster.png")


def test_a_plot_config_needs_an_enabled_field() -> None:
    class NoEnabled(FrozenConfig):
        figsize: float = 1.0

    with pytest.raises(ValueError, match="enabled"):
        register_plot("no_enabled", config_cls=NoEnabled, plot_fn=_plot, filename="x.png")


def test_a_function_gets_only_the_arguments_it_names() -> None:
    received = {}

    def plot(simulation, save_path, area=None):
        received.update(simulation=simulation, save_path=save_path, area=area)

    register_plot("by_name", plot)
    call_plot(
        registry_module.PLOT_REGISTRY["by_name"], "sim",
        begin=0.0, end=10.0, area="V1", save_path="out.png", show=False,
    )

    assert received == {"simulation": "sim", "save_path": "out.png", "area": "V1"}


def test_a_parameter_with_another_name_needs_a_default() -> None:
    def plot(simulation, color="k"):
        pass

    register_plot("own_default", plot)

    def bad(simulation, colour):
        pass

    with pytest.raises(ValueError, match="colour"):
        register_plot("own_no_default", bad)


def test_the_error_for_an_unknown_argument_lists_the_allowed_names() -> None:
    def plot(simulation, bogus):
        pass

    with pytest.raises(ValueError, match="save_path"):
        register_plot("bogus_plot", plot)


def test_filename_defaults_to_the_plot_name_and_config_is_optional() -> None:
    def plot(simulation, save_path):
        pass

    register_plot("defaults_plot", plot)

    spec = registry_module.PLOT_REGISTRY["defaults_plot"]
    assert spec.filename == "defaults_plot.png"
    assert spec.config_cls is None


def test_without_a_config_class_the_yaml_section_is_a_plain_dict() -> None:
    from microcircuit_lab.config import AnalysisConfig

    analysis_config = AnalysisConfig.model_validate({"my_plot": {"enabled": True, "color": "green"}})

    assert analysis_config.plot_config("my_plot", None) == {"enabled": True, "color": "green"}
    assert analysis_config.plot_config("absent_plot", None) == {}
