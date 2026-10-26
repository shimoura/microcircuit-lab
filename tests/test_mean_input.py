import math

import pytest

from microcircuit_lab.builder_tools import scale_network
from microcircuit_lab.network.load import assemble_network, read_network_files
from microcircuit_lab.network.mean_input import (
    full_mean_rates,
    indegree_matrix,
    mean_psc_matrix,
    network_mean_input,
)


def _load_toy():
    network_files = read_network_files("configs/network/toy")
    network = assemble_network(network_files)
    # toy's own reference.yaml has no published rates; the manual-vs-computed
    # tests below only need *some* rates to compare against themselves.
    return network.model_copy(
        update={
            "reference": network.reference.model_copy(
                update={"full_mean_rates": {name: 5.0 for name in network.populations}}
            )
        }
    )


def test_network_mean_input_manual():
    network = _load_toy()

    PSC = mean_psc_matrix(network)
    K = indegree_matrix(network)
    rates = full_mean_rates(network)

    manual = (PSC[0] * K[0] * rates).sum()

    computed = network_mean_input(
        mean_PSC_matrix=PSC,
        indegree_matrix=K,
        mean_rates=rates,
    )[0]

    assert manual == pytest.approx(computed)


def _scaled(network, **switches):
    return scale_network(network, N_scaling=0.2, K_scaling=0.2, scaled_from="toy", **switches)


def test_weight_scaling():
    """Default (preserve_variance): w -> w / sqrt(K); linear: w -> w / K."""

    network = _load_toy()
    weight = network.connections["weight.mean"][0]

    assert _scaled(network).connections["weight.mean"][0] == pytest.approx(weight / math.sqrt(0.2))
    linear = _scaled(network, preserve_variance=False)
    assert linear.connections["weight.mean"][0] == pytest.approx(weight / 0.2)


def test_identity_scaling_changes_nothing():
    network = _load_toy()
    derived = scale_network(network, N_scaling=1.0, K_scaling=1.0, scaled_from="toy")

    for name, pop in derived.populations.items():
        assert pop.size == network.populations[name].size
        assert pop.background_indegree == network.populations[name].background_indegree
        assert pop.neuron.parameters.I_e == network.populations[name].neuron.parameters.I_e


def test_downscaled_network_has_dc_compensation():
    derived = _scaled(_load_toy())
    assert any(pop.neuron.parameters.I_e != 0.0 for pop in derived.populations.values())


def test_preserve_variance_false_skips_dc_compensation():
    """Linear scaling preserves mean input on its own -- no bias to
    correct for, so DC compensation must not fire even though
    preserve_mean_input defaults to True."""

    for pop in _scaled(_load_toy(), preserve_variance=False).populations.values():
        assert pop.neuron.parameters.I_e == pytest.approx(0.0)


def test_preserve_mean_input_false_disables_dc_compensation():
    """With sqrt (variance-preserving) scaling still selected, turning off
    preserve_mean_input must disable the DC compensation that would
    otherwise fire for a downscaled network."""

    network = _load_toy()
    derived = _scaled(network, preserve_mean_input=False)

    for pop in derived.populations.values():
        assert pop.neuron.parameters.I_e == pytest.approx(0.0)
    # weight scaling itself is untouched by preserve_mean_input -- still sqrt
    expected = network.connections["weight.mean"][0] / math.sqrt(0.2)
    assert derived.connections["weight.mean"][0] == pytest.approx(expected)
