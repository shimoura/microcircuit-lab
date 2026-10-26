"""Tests for compute_reference_deviation / check_reference_rates."""

import pytest

from microcircuit_lab import Simulation
from microcircuit_lab.analysis import check_reference_rates, compute_reference_deviation
from microcircuit_lab.config.reference import ReferenceConfig
from microcircuit_lab.network.load import assemble_network, read_network_files


def _toy_simulation_with_reference(tmp_path, full_mean_rates: dict[str, float]) -> Simulation:
    network_files = read_network_files("configs/network/toy")
    config = assemble_network(network_files)
    config = config.model_copy(
        update={"reference": ReferenceConfig(full_mean_rates=full_mean_rates)}
    )

    from microcircuit_lab.config.simulation import SimulationConfig

    simulation_config_data = {
        "t_sim": 1000.0,
        "print_time": False,
        "output": {"output_dir": str(tmp_path), "overwrite": True},
    }

    simulation = Simulation(
        network=config,
        simulation_config=SimulationConfig.model_validate(simulation_config_data),
        network_name="toy",
        simulation_name="toy",
    )
    simulation.run()
    return simulation


def test_reference_deviation_requires_reference_data(tmp_path):
    simulation = Simulation.from_yaml(network_name="toy", simulation_name="toy")
    simulation.simulation_config = simulation.simulation_config.model_copy(
        update={
            "t_sim": 100.0,
            "print_time": False,
            "output": simulation.simulation_config.output.model_copy(
                update={"output_dir": tmp_path, "overwrite": True}
            ),
        }
    )
    simulation.run()  # toy's own reference.yaml is empty

    with pytest.raises(ValueError, match="reference"):
        compute_reference_deviation(simulation)


def test_reference_deviation_computed_correctly_for_matching_rates(tmp_path):
    # Real toy run at these settings produces ~20 Hz in both populations
    # (see configs/network/toy/populations.yaml's own comment); use that
    # as the reference so the deviation should come out near zero.
    simulation = _toy_simulation_with_reference(tmp_path, {"E": 19.887, "I": 20.380})

    deviations = compute_reference_deviation(simulation)

    assert set(deviations) == {"E", "I"}
    for value in deviations.values():
        assert abs(value) < 0.05  # within 5% of the real, matching run


def test_check_reference_rates_passes_within_tolerance(tmp_path):
    simulation = _toy_simulation_with_reference(tmp_path, {"E": 19.887, "I": 20.380})

    result = check_reference_rates(simulation, rtol=0.5)
    assert set(result) == {"E", "I"}


def test_check_reference_rates_fails_outside_tolerance(tmp_path):
    simulation = _toy_simulation_with_reference(tmp_path, {"E": 1000.0, "I": 1000.0})

    with pytest.raises(AssertionError, match="deviate from reference"):
        check_reference_rates(simulation, rtol=0.1)


def test_reference_deviation_raises_on_missing_population_key(tmp_path):
    simulation = _toy_simulation_with_reference(tmp_path, {"E": 19.887})  # missing "I"

    with pytest.raises(ValueError, match="No reference rate"):
        compute_reference_deviation(simulation)
