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


def test_network_mean_input_manual():
    network_files = read_network_directory("configs/network/pd14")

    network = NetworkConfigLoader(network_files).build()

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
    network_files = read_network_directory("configs/network/pd14")
    network = NetworkConfigLoader(network_files).build()
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
        name="L23_E",
        size=100,
        neuron=neuron,
        V0_mean=-58.0,
        V0_std=5.0,
        background_indegree=100.0,
    )

    network = NetworkConfig(
        populations={
            "L23_E": population,
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

    assert network.populations["L23_E"].size == 100

    #
    # derived scaled
    #

    assert derived.populations["L23_E"].size == 50


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
        name="L23_E",
        size=100,
        neuron=neuron,
        V0_mean=-58.0,
        V0_std=5.0,
        background_indegree=100.0,
    )

    network = NetworkConfig(
        populations={
            "L23_E": population,
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

    assert network.populations["L23_E"].background_indegree == 100

    #
    # derived scaled
    #

    assert derived.populations["L23_E"].background_indegree == 50


def test_weight_scaling():

    network_files = read_network_directory("configs/network/pd14")

    network_config = NetworkConfigLoader(network_files).build()

    derived = NetworkPreprocessor(network_config).process()

    K_scaling = network_config.scaling.K_scaling

    expected = psp_to_psc_iaf_psc_exp(
        psp=0.15,
        C_m=250.0,
        tau_m=10.0,
        tau_syn=0.5,
    ) / math.sqrt(K_scaling)

    assert derived.connections[0].weight.mean == pytest.approx(expected)


def test_identity_scaling():

    network_files = read_network_directory("configs/network/pd14")

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

    assert derived.populations["L23_E"].size == 20683

    assert derived.populations["L23_E"].background_indegree == 1600


def test_identity_scaling_has_zero_dc():

    network_files = read_network_directory("configs/network/pd14")

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

    network_files = read_network_directory("configs/network/pd14")

    network = NetworkConfigLoader(network_files).build()

    network = network.model_copy(
        update={
            "scaling": network.scaling.model_copy(
                update={
                    "N_scaling": 0.2,
                    "K_scaling": 0.2,
                }
            )
        }
    )

    derived = NetworkPreprocessor(network).process()

    assert any(pop.neuron.parameters.I_e != 0.0 for pop in derived.populations.values())


def test_preserve_variance_false_uses_linear_weight_scaling():
    """scaling.preserve_variance=False selects scale_weight (w -> w/K)
    instead of the default scale_weight_sqrt (w -> w/sqrt(K))."""

    network_files = read_network_directory("configs/network/pd14")
    network = NetworkConfigLoader(network_files).build()

    network = network.model_copy(
        update={
            "scaling": network.scaling.model_copy(
                update={"N_scaling": 0.2, "K_scaling": 0.2, "preserve_variance": False}
            )
        }
    )

    derived = NetworkPreprocessor(network).process()

    expected = psp_to_psc_iaf_psc_exp(
        psp=0.15, C_m=250.0, tau_m=10.0, tau_syn=0.5,
    ) / network.scaling.K_scaling  # linear, not sqrt

    assert derived.connections[0].weight.mean == pytest.approx(expected)


def test_preserve_variance_false_skips_dc_compensation():
    """Linear scaling preserves mean input on its own -- no bias to
    correct for, so DC compensation must not fire even though
    preserve_mean_input defaults to True."""

    network_files = read_network_directory("configs/network/pd14")
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

    network_files = read_network_directory("configs/network/pd14")
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
    expected = psp_to_psc_iaf_psc_exp(
        psp=0.15, C_m=250.0, tau_m=10.0, tau_syn=0.5,
    ) / math.sqrt(network.scaling.K_scaling)
    assert derived.connections[0].weight.mean == pytest.approx(expected)
