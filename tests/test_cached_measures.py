"""Tests for cached_population_firing_rates (analysis.firing_rates) and
cached_power_spectrum (analysis.power_spectrum)."""

from pathlib import Path

import pytest

import microcircuit_lab.analysis.firing_rates as firing_rates_module
from microcircuit_lab import Simulation
from microcircuit_lab.analysis import cached_population_firing_rates, cached_power_spectrum
from microcircuit_lab.analysis.cache import load_measures


def _run_toy_simulation(tmp_path: Path) -> Simulation:
    simulation = Simulation.from_yaml(network_name="toy", simulation_name="toy")
    simulation.simulation_config = simulation.simulation_config.model_copy(
        update={
            "t_sim": 300.0,
            "print_time": False,
            "output": simulation.simulation_config.output.model_copy(
                update={"output_dir": tmp_path, "overwrite": True}
            ),
        }
    )
    simulation.run()
    return simulation


def test_cached_population_firing_rates_saves_a_reusable_cache(tmp_path):
    simulation = _run_toy_simulation(tmp_path)

    rates = cached_population_firing_rates(simulation)

    assert load_measures(simulation.output_dir, "firing_rates") == rates


def test_cached_power_spectrum_saves_a_reusable_cache(tmp_path):
    simulation = _run_toy_simulation(tmp_path)

    spectra = cached_power_spectrum(simulation, method="welch")

    assert set(load_measures(simulation.output_dir, "power_spectrum")) == set(spectra)


def test_cached_population_firing_rates_uses_cache_without_recomputing(tmp_path, monkeypatch):
    simulation = _run_toy_simulation(tmp_path)
    cached_population_firing_rates(simulation)  # populates the cache

    def _must_not_be_called(*args, **kwargs):
        raise AssertionError("should reuse the cache, not recompute from spikes")

    monkeypatch.setattr(
        firing_rates_module, "compute_population_firing_rates", _must_not_be_called
    )

    cached_population_firing_rates(simulation)  # would raise above if it recomputed


def test_cached_population_firing_rates_recompute_true_ignores_cache(tmp_path):
    simulation = _run_toy_simulation(tmp_path)
    cached = cached_population_firing_rates(simulation)

    recomputed = cached_population_firing_rates(simulation, recompute=True)

    assert recomputed == cached  # same spikes, same result -- just not read from disk


def test_cached_measures_require_a_run_simulation():
    simulation = Simulation.from_yaml(network_name="toy", simulation_name="toy")

    with pytest.raises(RuntimeError, match="output_dir"):
        cached_population_firing_rates(simulation)
