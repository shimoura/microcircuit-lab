"""What the DC compensation of a scaled network needs, the error when it is
missing, and the record a scaled network carries."""

from __future__ import annotations

import pytest

from microcircuit_lab.builder_tools import (
    replace_background_by_mean_current,
    scale_network,
    write_network,
)
from microcircuit_lab.network.load import (
    assemble_network,
    read_network,
    read_network_files,
)


def _toy():
    """The toy network, whose reference.yaml has no rates."""
    return assemble_network(read_network_files("configs/network/toy"))


def _scaled(network, **switches):
    return scale_network(network, N_scaling=1.0, K_scaling=0.5, scaled_from="toy", **switches)


def test_a_missing_reference_rate_names_the_population() -> None:
    with pytest.raises(ValueError, match=r"has no rate for population\(s\) \['E', 'I'\]"):
        _scaled(_toy())


def test_no_reference_at_all_is_an_error_naming_the_populations() -> None:
    with pytest.raises(ValueError, match=r"has no rate for population\(s\) \['E', 'I'\]"):
        _scaled(_toy().model_copy(update={"reference": None}))


def test_no_compensation_needs_no_reference_rates() -> None:
    _scaled(_toy(), preserve_mean_input=False)


def test_background_only_compensation_works_without_reference() -> None:
    network = _toy()
    with_reference = _scaled(network, compensate_recurrent_input=False)
    without = _scaled(network.model_copy(update={"reference": None}), compensate_recurrent_input=False)

    I_e = {name: population.neuron.parameters.I_e for name, population in without.populations.items()}
    assert I_e == {name: population.neuron.parameters.I_e for name, population in with_reference.populations.items()}
    assert I_e["E"] > 0


def test_a_population_without_background_input_gets_no_background_current() -> None:
    network = _toy()
    network = network.model_copy(update={"poisson_background": {"E": network.poisson_background["E"]}})

    scaled = _scaled(network, compensate_recurrent_input=False)
    mean_current = replace_background_by_mean_current(network)

    for prepared in (scaled, mean_current):
        assert prepared.populations["E"].neuron.parameters.I_e > 0
        assert prepared.populations["I"].neuron.parameters.I_e == 0


def test_a_scaled_folder_records_how_and_is_not_scaled_again(tmp_path) -> None:
    scaled = _scaled(_toy(), compensate_recurrent_input=False)
    written = write_network(scaled, tmp_path / "toy_half")

    assert read_network(tmp_path / "toy_half") == written
    assert written.scaling.scaled_from == "toy" and written.scaling.parameters["K_scaling"] == 0.5
    assert written.scaling.scaled_with == "microcircuit_lab.builder_tools.scaling.scale_network"
    with pytest.raises(ValueError, match="already scaled"):
        _scaled(written)


def test_an_old_scaling_file_fails_with_the_new_way(tmp_path) -> None:
    folder = tmp_path / "toy"
    write_network(_toy(), folder)
    (folder / "scaling.yaml").write_text("N_scaling: 0.5\nK_scaling: 0.5\n")
    (folder / "network.yaml").write_text((folder / "network.yaml").read_text() + "scaling: scaling.yaml\n")

    with pytest.raises(ValueError, match="no longer scales the network when it runs"):
        read_network(folder)
