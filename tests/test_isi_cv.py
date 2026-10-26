"""Tests for ISI-CV (spike-train irregularity) analysis.

Synthetic tests exercise compute_neuron_isi_cv's math directly against a
minimal stand-in for a Run (no NEST/backend needed, so
these run in milliseconds); one integration test runs a real toy
simulation end to end.
"""

import types

import numpy as np
import pytest

from microcircuit_lab import Simulation, read_run
from microcircuit_lab.analysis import compute_population_isi_cv, plot_isi_cv
from microcircuit_lab.analysis.isi_cv import compute_neuron_isi_cv
from microcircuit_lab.run_folder import Spikes


class _FakeRun:
    """Minimal stand-in for a Run, exposing only what compute_neuron_isi_cv touches."""

    def __init__(self, populations: dict[str, list[int]], events: dict[str, dict]):
        self._populations = populations
        self._events = events
        self.simulation = types.SimpleNamespace(t_sim=1000.0)
        self.network = types.SimpleNamespace(populations=dict.fromkeys(populations))

    def node_ids(self, name):
        return np.array(self._populations[name])

    def spikes(self, name):
        return Spikes(self._events[name]["senders"], self._events[name]["times"])


def test_regular_spike_train_has_near_zero_cv():
    times = np.arange(10.0, 100.0, 10.0)  # perfectly regular, 10 ms period
    senders = np.full(len(times), 1)

    sim = _FakeRun(populations={"E": [1]}, events={"E": {"times": times, "senders": senders}})

    cv = compute_neuron_isi_cv(sim, populations=["E"])
    assert cv["E"][0] == pytest.approx(0.0, abs=1e-9)


def test_neurons_below_min_spikes_are_nan():
    times = np.array([10.0, 20.0])  # 1 ISI; min_spikes=3 needs at least 2
    senders = np.array([1, 1])

    sim = _FakeRun(populations={"E": [1]}, events={"E": {"times": times, "senders": senders}})

    cv = compute_neuron_isi_cv(sim, populations=["E"], min_spikes=3)
    assert np.isnan(cv["E"][0])


def test_population_mean_ignores_nan_neurons():
    # neuron 1: 3 regular spikes (CV=0); neuron 2: 1 spike (undefined, NaN)
    times = np.array([10.0, 20.0, 30.0, 10.0])
    senders = np.array([1, 1, 1, 2])

    sim = _FakeRun(
        populations={"E": [1, 2]}, events={"E": {"times": times, "senders": senders}}
    )

    means = compute_population_isi_cv(sim, populations=["E"], min_spikes=3)
    assert means["E"] == pytest.approx(0.0, abs=1e-9)


def test_compute_neuron_isi_cv_rejects_min_spikes_below_two():
    sim = _FakeRun(populations={"E": [1]}, events={"E": {"times": np.array([]), "senders": np.array([])}})

    with pytest.raises(ValueError, match="min_spikes"):
        compute_neuron_isi_cv(sim, populations=["E"], min_spikes=1)


def test_toy_network_isi_cv_end_to_end(tmp_path):
    simulation = Simulation.from_yaml(network_name="toy", simulation_name="toy")
    simulation.simulation_config = simulation.simulation_config.model_copy(
        update={
            "t_sim": 1000.0,
            "print_time": False,
            "output": simulation.simulation_config.output.model_copy(
                update={"output_dir": tmp_path, "overwrite": True}
            ),
        }
    )
    simulation.run()
    run = read_run(tmp_path)

    means = compute_population_isi_cv(run)
    assert set(means) == {"E", "I"}
    for value in means.values():
        assert 0.0 <= value < 3.0  # sane range; not asserting a specific regime

    fig, ax = plot_isi_cv(run, show=False)
    assert ax.get_xlabel() == "ISI CV"
    fig.clf()
