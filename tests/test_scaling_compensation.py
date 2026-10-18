"""What the DC compensation of a scaled network needs, and what it says when it is missing."""

from __future__ import annotations

import logging

import pytest

from microcircuit_lab.config.network import ScalingConfig
from microcircuit_lab.io.config import NetworkConfigLoader
from microcircuit_lab.io.files import read_network_directory
from microcircuit_lab.network.preprocessing import NetworkPreprocessor


def _toy(**scaling) -> object:
    """The toy network, whose reference.yaml has no rates, scaled as given."""
    network = NetworkConfigLoader(read_network_directory("configs/network/toy")).build()
    return network.model_copy(update={"scaling": ScalingConfig(**scaling)})


def test_a_missing_reference_rate_names_the_population() -> None:
    with pytest.raises(ValueError, match=r"has no rate for population\(s\) \['E', 'I'\]"):
        NetworkPreprocessor(_toy(K_scaling=0.5)).process()


def test_background_only_compensation_needs_no_reference_rates() -> None:
    NetworkPreprocessor(_toy(K_scaling=0.5, compensate_recurrent_input=False)).process()


def test_no_compensation_needs_no_reference_rates() -> None:
    NetworkPreprocessor(_toy(K_scaling=0.5, preserve_mean_input=False)).process()


def test_no_reference_at_all_warns_instead_of_silently_skipping(caplog) -> None:
    network = _toy(K_scaling=0.5).model_copy(update={"reference": None})

    with caplog.at_level(logging.WARNING):
        NetworkPreprocessor(network).process()

    assert "no DC compensation" in caplog.text


def test_an_unscaled_network_does_not_warn(caplog) -> None:
    network = _toy().model_copy(update={"reference": None})

    with caplog.at_level(logging.WARNING):
        NetworkPreprocessor(network).process()

    assert "no DC compensation" not in caplog.text
