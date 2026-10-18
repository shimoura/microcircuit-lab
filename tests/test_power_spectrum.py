"""Tests for population rate power-spectrum analysis."""

import numpy as np
import pytest

from microcircuit_lab import Simulation
from microcircuit_lab.analysis import (
    POWER_SPECTRUM_METHODS,
    PowerSpectrumPlotConfig,
    compute_power_spectrum,
    plot_power_spectrum,
)
from microcircuit_lab.analysis.power_spectrum import _multitaper, _periodogram, _welch


def _run_toy_simulation(tmp_path, t_sim=500.0):
    """A short toy run, writing to pytest's tmp_path instead of the
    project's real output/ directory."""

    simulation = Simulation.from_yaml(network_name="toy", simulation_name="toy")
    simulation.simulation_config = simulation.simulation_config.model_copy(
        update={
            "t_sim": t_sim,
            "print_time": False,
            "output": simulation.simulation_config.output.model_copy(
                update={"output_dir": tmp_path, "overwrite": True}
            ),
        }
    )
    simulation.run()
    return simulation


@pytest.mark.parametrize("estimator", [_periodogram, _welch, _multitaper])
def test_estimators_recover_a_known_frequency(estimator):
    fs = 1000.0  # Hz
    duration_s = 4.0
    t = np.arange(0.0, duration_s, 1.0 / fs)
    signal = np.sin(2 * np.pi * 40.0 * t)  # pure 40 Hz tone

    freqs, power = estimator(signal, fs)

    assert freqs[np.argmax(power)] == pytest.approx(40.0, abs=1.0)


def test_compute_power_spectrum_on_toy_simulation(tmp_path):
    simulation = _run_toy_simulation(tmp_path)

    spectra = compute_power_spectrum(simulation, bin_size=1.0, method="welch")

    assert set(spectra) == {"E", "I"}
    for freqs, power in spectra.values():
        assert len(freqs) == len(power)
        assert freqs[0] == 0.0
        assert np.all(np.diff(freqs) > 0)
        assert np.all(power >= 0.0)


def test_compute_power_spectrum_rejects_unknown_method(tmp_path):
    simulation = _run_toy_simulation(tmp_path, t_sim=200.0)

    with pytest.raises(ValueError, match="Unknown power spectrum method"):
        compute_power_spectrum(simulation, method="not-a-real-method")


def test_all_registered_methods_are_usable(tmp_path):
    simulation = _run_toy_simulation(tmp_path, t_sim=200.0)

    for method in POWER_SPECTRUM_METHODS:
        spectra = compute_power_spectrum(simulation, method=method)
        assert set(spectra) == {"E", "I"}


def test_plot_power_spectrum_grid_layout(tmp_path):
    """Toy's E/I populations share no layer, so they land in one row,
    one column each (see analysis.power_spectrum._grid_layout)."""

    simulation = _run_toy_simulation(tmp_path, t_sim=200.0)

    fig, axes = plot_power_spectrum(simulation, show=False)

    assert axes.shape == (1, 2)
    titles = {ax.get_title() for ax in axes.flat}
    assert titles == {"E", "I"}
    fig.clf()


def test_power_spectrum_method_kwargs_from_config(tmp_path):
    """PowerSpectrumPlotConfig.method_kwargs (e.g. multitaper's `bandwidth`)
    reaches the estimator when plot_power_spectrum's own method_kwargs
    argument is left unset."""

    simulation = _run_toy_simulation(tmp_path)

    config = PowerSpectrumPlotConfig(method="multitaper", method_kwargs={"bandwidth": 8.0})
    fig, axes = plot_power_spectrum(simulation, config=config, show=False)
    fig.clf()


def test_grid_layout_groups_shared_layer_into_one_row():
    from microcircuit_lab.analysis.power_spectrum import _grid_layout

    cells = _grid_layout(["L23_E", "L23_I", "L4_E", "L4_I"])

    assert cells[(0, 0)] == ["L23_E"]
    assert cells[(0, 1)] == ["L23_I"]
    assert cells[(1, 0)] == ["L4_E"]
    assert cells[(1, 1)] == ["L4_I"]


def test_grid_layout_handles_areas_with_different_cell_types():
    from microcircuit_lab.analysis.power_spectrum import _grid_layout

    cells = _grid_layout(["A__L23_E", "A__L23_PV", "A__L4_E", "B__L23_E", "B__L23_VIP"])

    assert cells[(0, 0)] == ["A__L23_E"]
    assert cells[(0, 1)] == ["A__L23_PV"]
    assert cells[(1, 0)] == ["A__L4_E"]
    assert cells[(2, 0)] == ["B__L23_E"]
    assert cells[(2, 2)] == ["B__L23_VIP"]
