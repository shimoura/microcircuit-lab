"""`scripts/run_simulation.py --area all`: one set of plots per area."""

import importlib.util
import sys
from pathlib import Path

import pytest

from microcircuit_lab import Simulation
from microcircuit_lab.analysis import PLOT_REGISTRY, PlotSpec
from microcircuit_lab.config.simulation import SimulationConfig
from microcircuit_lab.io.config import NetworkConfigLoader
from microcircuit_lab.io.files import read_network_directory
from microcircuit_lab.network import Network, NetworkPreprocessor



def _toy_network() -> Network:
    network_files = read_network_directory("configs/network/toy")
    config = NetworkConfigLoader(network_files).build()
    config = NetworkPreprocessor(config).process()
    return Network(config)


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_simulation.py"


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("run_simulation_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def toy_run(tmp_path_factory):
    out = tmp_path_factory.mktemp("toy_run")
    simulation_config = SimulationConfig.model_validate(
        {
            "t_sim": 50.0,
            "local_num_threads": 1,
            "print_time": False,
            "output": {"output_dir": str(out), "overwrite": True},
        }
    )
    sim = Simulation(
        network=_toy_network(),
        simulation_config=simulation_config,
        backend="nest",
        network_name="toy",
        simulation_name="toy",
    )
    sim.run()
    return sim.output_dir


def _argv(run_dir, area):
    return ["run_simulation.py", "--run-dir", str(run_dir), "--area", area]


def _recording_registry(calls):
    def fake_plot(simulation, *, area, save_path, **kwargs):
        calls.append((area, Path(save_path)))

    return {
        "raster": PlotSpec(
            config_cls=PLOT_REGISTRY["raster"].config_cls,
            plot_fn=fake_plot,
            filename="raster.png",
        )
    }


def test_area_all_on_single_area_network_exits(script, toy_run, monkeypatch):
    monkeypatch.setattr(sys, "argv", _argv(toy_run, "all"))
    with pytest.raises(SystemExit, match="multi-area"):
        script.main()


def test_area_all_plots_each_area_into_its_own_folder(script, toy_run, monkeypatch):
    calls = []
    monkeypatch.setattr(script, "PLOT_REGISTRY", _recording_registry(calls))
    monkeypatch.setattr(script, "list_areas", lambda simulation: ["A", "B"])
    monkeypatch.setattr(sys, "argv", _argv(toy_run, "all"))
    script.main()

    plots = toy_run / "plots"
    assert calls == [("A", plots / "A" / "raster.png"), ("B", plots / "B" / "raster.png")]


def test_single_area_plots_into_plots_dir(script, toy_run, monkeypatch):
    calls = []
    monkeypatch.setattr(script, "PLOT_REGISTRY", _recording_registry(calls))
    monkeypatch.setattr(sys, "argv", _argv(toy_run, "A"))
    script.main()

    assert calls == [("A", toy_run / "plots" / "raster.png")]
