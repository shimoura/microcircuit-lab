"""Tests for cached_population_firing_rates (analysis.firing_rates) and
cached_power_spectrum (analysis.power_spectrum)."""

from pathlib import Path

import microcircuit_lab.analysis.firing_rates as firing_rates_module
from microcircuit_lab import Simulation, read_run
from microcircuit_lab.analysis import (
    cached_population_firing_rates,
    cached_power_spectrum,
)
from microcircuit_lab.analysis.measure_files import load_measures
from microcircuit_lab.run_folder import Run


def _run_toy(tmp_path: Path) -> Run:
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
    return read_run(tmp_path)


def test_cached_population_firing_rates_saves_a_reusable_cache(tmp_path):
    run = _run_toy(tmp_path)

    rates = cached_population_firing_rates(run)

    assert load_measures(run.folder, "firing_rates") == rates


def test_cached_power_spectrum_saves_a_reusable_cache(tmp_path):
    run = _run_toy(tmp_path)

    spectra = cached_power_spectrum(run, method="welch")

    assert set(load_measures(run.folder, "power_spectrum")) == set(spectra)


def test_cached_population_firing_rates_uses_cache_without_recomputing(tmp_path, monkeypatch):
    run = _run_toy(tmp_path)
    cached_population_firing_rates(run)  # populates the cache

    def _must_not_be_called(*args, **kwargs):
        raise AssertionError("should reuse the cache, not recompute from spikes")

    monkeypatch.setattr(
        firing_rates_module, "compute_population_firing_rates", _must_not_be_called
    )

    cached_population_firing_rates(run)  # would raise above if it recomputed


def test_cached_population_firing_rates_recompute_true_ignores_cache(tmp_path):
    run = _run_toy(tmp_path)
    cached = cached_population_firing_rates(run)

    recomputed = cached_population_firing_rates(run, recompute=True)

    assert recomputed == cached  # same spikes, same result -- just not read from disk

