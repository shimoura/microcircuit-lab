"""What the DC compensation of a scaled network needs, and what it says when it is missing."""

from __future__ import annotations

import logging

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


def test_no_reference_at_all_warns_instead_of_silently_skipping(caplog) -> None:
    network = _toy(K_scaling=0.5).model_copy(update={"reference": None})

    with caplog.at_level(logging.WARNING):
        prepare_network(network)

    assert "no DC compensation" in caplog.text


def test_an_unscaled_network_does_not_warn(caplog) -> None:
    network = _toy().model_copy(update={"reference": None})

    with caplog.at_level(logging.WARNING):
        prepare_network(network)

    assert "no DC compensation" not in caplog.text
