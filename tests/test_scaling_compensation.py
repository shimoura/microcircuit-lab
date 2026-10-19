"""What the DC compensation of a scaled network needs, and the error when it is missing."""

from __future__ import annotations

import pytest

from microcircuit_lab.config.scaling import ScalingConfig
from microcircuit_lab.network.load import assemble_network, read_network_files
from microcircuit_lab.network.prepare import prepare_network


def _toy(**scaling) -> object:
    """The toy network, whose reference.yaml has no rates, scaled as given."""
    network = assemble_network(read_network_files("configs/network/toy"))
    return network.model_copy(update={"scaling": ScalingConfig(**scaling)})


def test_a_missing_reference_rate_names_the_population() -> None:
    with pytest.raises(ValueError, match=r"has no rate for population\(s\) \['E', 'I'\]"):
        prepare_network(_toy(K_scaling=0.5))


def test_background_only_compensation_needs_no_reference_rates() -> None:
    prepare_network(_toy(K_scaling=0.5, compensate_recurrent_input=False))


def test_no_compensation_needs_no_reference_rates() -> None:
    prepare_network(_toy(K_scaling=0.5, preserve_mean_input=False))


def test_no_reference_at_all_is_an_error_naming_the_populations() -> None:
    network = _toy(K_scaling=0.5).model_copy(update={"reference": None})

    with pytest.raises(ValueError, match=r"has no rate for population\(s\) \['E', 'I'\]"):
        prepare_network(network)


def test_background_only_compensation_works_without_reference() -> None:
    network = _toy(K_scaling=0.5, compensate_recurrent_input=False)
    without = network.model_copy(update={"reference": None})

    I_e = {
        name: population.neuron.parameters.I_e
        for name, population in prepare_network(without).populations.items()
    }
    assert I_e == {
        name: population.neuron.parameters.I_e
        for name, population in prepare_network(network).populations.items()
    }
    assert I_e["E"] > 0


def test_a_population_without_background_input_gets_no_background_current() -> None:
    network = _toy(K_scaling=0.5, compensate_recurrent_input=False)
    network = network.model_copy(
        update={"background_inputs": {"E": network.background_inputs["E"]}}
    )

    scaled = prepare_network(network)
    mean_current = prepare_network(
        network.model_copy(update={"scaling": ScalingConfig(), "background_mode": "mean_current"})
    )

    for prepared in (scaled, mean_current):
        assert prepared.populations["E"].neuron.parameters.I_e > 0
        assert prepared.populations["I"].neuron.parameters.I_e == 0
