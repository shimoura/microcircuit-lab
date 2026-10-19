"""`microcircuit-lab run --area all`: one set of plots per area."""

import importlib
import json
import sys
from pathlib import Path

import pytest

from microcircuit_lab import Simulation
from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.analysis import PLOT_REGISTRY, PlotSpec
from microcircuit_lab.config.simulation import SimulationConfig
from microcircuit_lab.network.load import assemble_network, read_network_files
from microcircuit_lab.network.prepare import prepare_network



def _toy_network() -> NetworkConfig:
    network_files = read_network_files("configs/network/toy")
    config = assemble_network(network_files)
    config = prepare_network(config)
    return config


@pytest.fixture(scope="module")
def script():
    return importlib.import_module("microcircuit_lab.cli.run")


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
    return ["microcircuit-lab run", "--run-dir", str(run_dir), "--area", area]


def _recording_registry(calls):
    def fake_plot(simulation, area, save_path):
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


def test_a_plot_from_the_project_analyses_folder_runs(
    script, toy_run, tmp_path, monkeypatch, request
):
    """A plot module in ./analyses/ gets its own --<name> flag and is saved
    under plots/ and listed in metadata.json, with no change to the core."""
    folder = tmp_path / "analyses"
    folder.mkdir()
    (folder / "e2e_plot.py").write_text(
        "from pathlib import Path\n"
        "from microcircuit_lab.analysis import register_plot\n\n\n"
        "def plot(simulation, save_path):\n"
        "    Path(save_path).write_text('plot')\n\n\n"
        "register_plot('e2e_plot', plot, filename='e2e_plot.txt')\n"
    )
    request.addfinalizer(lambda: PLOT_REGISTRY.pop("e2e_plot", None))
    request.addfinalizer(lambda: sys.modules.pop("analyses.e2e_plot", None))
    request.addfinalizer(lambda: sys.modules.pop("analyses", None))
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    config_dir = Path(__file__).resolve().parents[1] / "configs"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "microcircuit-lab run", "--run-dir", str(toy_run), "--config-dir", str(config_dir),
            "--no-raster", "--no-firing-rates", "--no-power-spectrum", "--no-isi-cv",
            "--e2e-plot",
        ],
    )
    script.main()

    assert (toy_run / "plots" / "e2e_plot.txt").read_text() == "plot"
    metadata = json.loads((toy_run / "metadata.json").read_text())
    assert "plots/e2e_plot.txt" in metadata["artifacts"]["plots"]
