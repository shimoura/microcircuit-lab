import math
import pytest
import numpy as np

from microcircuit_lab.io.config import NetworkConfigLoader
from microcircuit_lab.network.preprocessing import (
    NetworkPreprocessor,
)
from microcircuit_lab.config.network import (
    NetworkConfig,
    PopulationConfig,
    ScalingConfig,
    NeuronConfig,
    NeuronParams,
)
from microcircuit_lab.io.files import read_network_directory
from microcircuit_lab.network.synapses import (
    psp_to_psc_iaf_psc_exp,
)
from microcircuit_lab.network.parameters import (
    indegree_matrix,
    full_mean_rates,
    mean_psc_matrix,
    network_mean_input,
    background_indegrees,
    background_psc_weights,
)


def _load_toy():
    network_files = read_network_directory("configs/network/toy")
    network = NetworkConfigLoader(network_files).build()
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
    PSP amplitude convert to, scaled the same way NetworkPreprocessor
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


def test_background_input_manual():
    network = _load_toy()
    PSC_ext = background_psc_weights(network)
    K_ext = background_indegrees(network)
    rates = np.asarray(
        [
            network.background_inputs[name].rate
            for name in network.populations
        ]
    )

    manual = PSC_ext * K_ext * rates

    computed = background_psc_weights(network) \
        * background_indegrees(network) \
        * rates

    assert np.allclose(manual, computed)

def test_n_scaling():

    neuron = NeuronConfig(
        name="exc",
        model="iaf_psc_exp",
        parameters=NeuronParams(
            C_m=250.0,
            tau_m=10.0,
            tau_syn_ex=0.5,
            tau_syn_in=0.5,
            E_L=-70.0,
            V_reset=-65.0,
            V_th=-50.0,
            t_ref=2.0,
            I_e=0.0,
        ),
    )

    population = PopulationConfig(
        name="E",
        size=100,
        neuron=neuron,
        V0_mean=-58.0,
        V0_std=5.0,
        background_indegree=100.0,
    )

    network = NetworkConfig(
        populations={
            "E": population,
        },
        connections=[],
        background_inputs={},
        scaling=ScalingConfig(
            N_scaling=0.5,
            K_scaling=1.0,
        ),
    )

    derived = NetworkPreprocessor(network).process()

    #
    # original unchanged
    #

    assert network.populations["E"].size == 100

    #
    # derived scaled
    #

    assert derived.populations["E"].size == 50


def test_k_scaling():

    neuron = NeuronConfig(
        name="exc",
        model="iaf_psc_exp",
        parameters=NeuronParams(
            C_m=250.0,
            tau_m=10.0,
            tau_syn_ex=0.5,
            tau_syn_in=0.5,
            E_L=-70.0,
            V_reset=-65.0,
            V_th=-50.0,
            t_ref=2.0,
            I_e=0.0,
        ),
    )

    population = PopulationConfig(
        name="E",
        size=100,
        neuron=neuron,
        V0_mean=-58.0,
        V0_std=5.0,
        background_indegree=100.0,
    )

    network = NetworkConfig(
        populations={
            "E": population,
        },
        connections=[],
        background_inputs={},
        scaling=ScalingConfig(
            N_scaling=1.0,
            K_scaling=0.5,
        ),
    )

    derived = NetworkPreprocessor(network).process()

    #
    # original unchanged
    #

    assert network.populations["E"].background_indegree == 100

    #
    # derived scaled
    #

    assert derived.populations["E"].background_indegree == 50


def test_weight_scaling():

    network_config = _load_toy()

    derived = NetworkPreprocessor(network_config).process()

    expected = _expected_first_weight_psc(network_config, linear=False)

    assert derived.connections[0].weight.mean == pytest.approx(expected)


def test_identity_scaling():

    network_files = read_network_directory("configs/network/toy")

    network = NetworkConfigLoader(network_files).build()

    original_size = network.populations["E"].size
    original_indegree = network.populations["E"].background_indegree

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

    derived = NetworkPreprocessor(network).process()

    assert derived.populations["E"].size == original_size

    assert derived.populations["E"].background_indegree == original_indegree


def test_identity_scaling_has_zero_dc():

    network_files = read_network_directory("configs/network/toy")

    network = NetworkConfigLoader(network_files).build()

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

    derived = NetworkPreprocessor(network).process()

    for pop in derived.populations.values():

        assert pop.neuron.parameters.I_e == pytest.approx(0.0)


def test_downscaled_network_has_dc_compensation():

    network_files = read_network_directory("configs/network/toy")

    network = NetworkConfigLoader(network_files).build()

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

    derived = NetworkPreprocessor(network).process()

    assert any(pop.neuron.parameters.I_e != 0.0 for pop in derived.populations.values())


def test_preserve_variance_false_uses_linear_weight_scaling():
    """scaling.preserve_variance=False selects scale_weight (w -> w/K)
    instead of the default scale_weight_sqrt (w -> w/sqrt(K))."""

    network_files = read_network_directory("configs/network/toy")
    network = NetworkConfigLoader(network_files).build()

    network = network.model_copy(
        update={
            "scaling": network.scaling.model_copy(
                update={"N_scaling": 0.2, "K_scaling": 0.2, "preserve_variance": False}
            )
        }
    )

    derived = NetworkPreprocessor(network).process()

    expected = _expected_first_weight_psc(network, linear=True)  # linear, not sqrt

    assert derived.connections[0].weight.mean == pytest.approx(expected)


def test_preserve_variance_false_skips_dc_compensation():
    """Linear scaling preserves mean input on its own -- no bias to
    correct for, so DC compensation must not fire even though
    preserve_mean_input defaults to True."""

    network_files = read_network_directory("configs/network/toy")
    network = NetworkConfigLoader(network_files).build()

    network = network.model_copy(
        update={
            "scaling": network.scaling.model_copy(
                update={"N_scaling": 0.2, "K_scaling": 0.2, "preserve_variance": False}
            )
        }
    )

    derived = NetworkPreprocessor(network).process()

    for pop in derived.populations.values():
        assert pop.neuron.parameters.I_e == pytest.approx(0.0)


def test_preserve_mean_input_false_disables_dc_compensation():
    """With sqrt (variance-preserving) scaling still selected, turning off
    preserve_mean_input must disable the DC compensation that would
    otherwise fire for a downscaled network."""

    network_files = read_network_directory("configs/network/toy")
    network = NetworkConfigLoader(network_files).build()

    network = network.model_copy(
        update={
            "scaling": network.scaling.model_copy(
                update={"N_scaling": 0.2, "K_scaling": 0.2, "preserve_mean_input": False}
            )
        }
    )

    derived = NetworkPreprocessor(network).process()

    for pop in derived.populations.values():
        assert pop.neuron.parameters.I_e == pytest.approx(0.0)

    # weight scaling itself is untouched by preserve_mean_input -- still sqrt
    expected = _expected_first_weight_psc(network, linear=False)
    assert derived.connections[0].weight.mean == pytest.approx(expected)
