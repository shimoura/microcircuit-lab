import math
import pytest

from microcircuit_lab.network.prepare import prepare_network
from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.network.load import assemble_network, read_network_files
from microcircuit_lab.network.units import (
    psp_to_psc_iaf_psc_exp,
)
from microcircuit_lab.network.quantities import (
    indegree_matrix,
    full_mean_rates,
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


def _expected_first_weight_psc(network: NetworkConfig, *, linear: bool) -> float:
    """The PSC a network's own neuron parameters and first connection's
    PSP amplitude convert to, scaled the same way prepare_network
    would (linear w -> w/K, or sqrt-preserving w -> w/sqrt(K))."""

    first = network.connections[0]
    target_params = network.populations[first.target].neuron.parameters

    psc = psp_to_psc_iaf_psc_exp(
        psp=first.weight.mean,
        C_m=target_params.C_m,
        tau_m=target_params.tau_m,
        tau_syn=target_params.tau_syn_ex,
    )
    K_scaling = network.scaling.K_scaling
    return psc / K_scaling if linear else psc / math.sqrt(K_scaling)


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


def test_weight_scaling():

    network_config = _load_toy()

    derived = prepare_network(network_config)

    expected = _expected_first_weight_psc(network_config, linear=False)

    assert derived.connections[0].weight.mean == pytest.approx(expected)


def test_identity_scaling_changes_nothing():

    network_files = read_network_files("configs/network/toy")

    network = assemble_network(network_files)

    network = network.model_copy(
        update={
            "scaling": network.scaling.model_copy(
                update={
                    "N_scaling": 1.0,
                    "K_scaling": 1.0,
                }
            )
        }
    )

    derived = prepare_network(network)

    for name, pop in derived.populations.items():
        assert pop.size == network.populations[name].size
        assert pop.background_indegree == network.populations[name].background_indegree
        assert pop.neuron.parameters.I_e == pytest.approx(0.0)


def test_downscaled_network_has_dc_compensation():

    network_files = read_network_files("configs/network/toy")

    network = assemble_network(network_files)

    network = network.model_copy(
        update={
            # Recurrent-input compensation needs reference rates to compute
            # against; toy's own reference.yaml has none.
            "reference": network.reference.model_copy(
                update={"full_mean_rates": {name: 5.0 for name in network.populations}}
            ),
            "scaling": network.scaling.model_copy(
                update={
                    "N_scaling": 0.2,
                    "K_scaling": 0.2,
                }
            ),
        }
    )

    derived = prepare_network(network)

    assert any(pop.neuron.parameters.I_e != 0.0 for pop in derived.populations.values())


def test_preserve_variance_false_uses_linear_weight_scaling():
    """scaling.preserve_variance=False selects scale_weight (w -> w/K)
    instead of the default scale_weight_sqrt (w -> w/sqrt(K))."""

    network_files = read_network_files("configs/network/toy")
    network = assemble_network(network_files)

    network = network.model_copy(
        update={
            "scaling": network.scaling.model_copy(
                update={"N_scaling": 0.2, "K_scaling": 0.2, "preserve_variance": False}
            )
        }
    )

    derived = prepare_network(network)

    expected = _expected_first_weight_psc(network, linear=True)  # linear, not sqrt

    assert derived.connections[0].weight.mean == pytest.approx(expected)


def test_preserve_variance_false_skips_dc_compensation():
    """Linear scaling preserves mean input on its own -- no bias to
    correct for, so DC compensation must not fire even though
    preserve_mean_input defaults to True."""

    network_files = read_network_files("configs/network/toy")
    network = assemble_network(network_files)

    network = network.model_copy(
        update={
            "scaling": network.scaling.model_copy(
                update={"N_scaling": 0.2, "K_scaling": 0.2, "preserve_variance": False}
            )
        }
    )

    derived = prepare_network(network)

    for pop in derived.populations.values():
        assert pop.neuron.parameters.I_e == pytest.approx(0.0)


def test_preserve_mean_input_false_disables_dc_compensation():
    """With sqrt (variance-preserving) scaling still selected, turning off
    preserve_mean_input must disable the DC compensation that would
    otherwise fire for a downscaled network."""

    network_files = read_network_files("configs/network/toy")
    network = assemble_network(network_files)

    network = network.model_copy(
        update={
            "scaling": network.scaling.model_copy(
                update={"N_scaling": 0.2, "K_scaling": 0.2, "preserve_mean_input": False}
            )
        }
    )

    derived = prepare_network(network)

    for pop in derived.populations.values():
        assert pop.neuron.parameters.I_e == pytest.approx(0.0)

    # weight scaling itself is untouched by preserve_mean_input -- still sqrt
    expected = _expected_first_weight_psc(network, linear=False)
    assert derived.connections[0].weight.mean == pytest.approx(expected)
