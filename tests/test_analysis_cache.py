"""Tests for saving/loading computed analysis results (analysis.cache)."""

from pathlib import Path

import numpy as np

from microcircuit_lab.analysis.cache import load_measures, load_or_compute, save_measures


def test_scalar_measures_roundtrip(tmp_path: Path) -> None:
    rates = {"E": 12.5, "I": 8.3}

    save_measures(tmp_path, "firing_rates", rates)
    loaded = load_measures(tmp_path, "firing_rates")

    assert loaded == rates
    assert all(isinstance(value, float) for value in loaded.values())


def test_spectrum_measures_roundtrip(tmp_path: Path) -> None:
    freqs = np.linspace(0.0, 100.0, 50)
    spectra = {
        "E": (freqs, np.random.default_rng(0).random(50)),
        "I": (freqs, np.random.default_rng(1).random(50)),
    }

    save_measures(tmp_path, "power_spectrum", spectra)
    loaded = load_measures(tmp_path, "power_spectrum")

    assert set(loaded) == {"E", "I"}
    for population, (expected_freqs, expected_power) in spectra.items():
        loaded_freqs, loaded_power = loaded[population]
        assert np.allclose(loaded_freqs, expected_freqs)
        assert np.allclose(loaded_power, expected_power)


def test_load_measures_returns_none_when_not_cached(tmp_path: Path) -> None:
    assert load_measures(tmp_path, "firing_rates") is None


def test_save_measures_writes_under_measures_subdirectory(tmp_path: Path) -> None:
    path = save_measures(tmp_path, "firing_rates", {"E": 1.0})

    assert path == tmp_path / "measures" / "firing_rates.npz"
    assert path.exists()


def test_load_or_compute_computes_and_saves_when_not_cached(tmp_path: Path) -> None:
    calls = []

    def compute():
        calls.append(1)
        return {"E": 1.0}

    result = load_or_compute(tmp_path, "firing_rates", compute)

    assert result == {"E": 1.0}
    assert len(calls) == 1
    assert load_measures(tmp_path, "firing_rates") == {"E": 1.0}


def test_load_or_compute_reuses_cache_without_calling_compute(tmp_path: Path) -> None:
    save_measures(tmp_path, "firing_rates", {"E": 1.0})

    def compute():
        raise AssertionError("should not be called when a cache is present")

    result = load_or_compute(tmp_path, "firing_rates", compute)

    assert result == {"E": 1.0}


def test_load_or_compute_recompute_true_ignores_cache(tmp_path: Path) -> None:
    save_measures(tmp_path, "firing_rates", {"E": 1.0})

    result = load_or_compute(tmp_path, "firing_rates", lambda: {"E": 2.0}, recompute=True)

    assert result == {"E": 2.0}
    assert load_measures(tmp_path, "firing_rates") == {"E": 2.0}  # overwritten


def test_load_or_compute_save_false_does_not_write_cache(tmp_path: Path) -> None:
    result = load_or_compute(tmp_path, "firing_rates", lambda: {"E": 1.0}, save=False)

    assert result == {"E": 1.0}
    assert load_measures(tmp_path, "firing_rates") is None
