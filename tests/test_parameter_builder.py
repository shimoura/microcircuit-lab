import math
import pytest

from human_microcircuit.builders.config_builder import ConfigBuilder
from human_microcircuit.builders.parameter_builder import (
    ParameterBuilder,
)
from human_microcircuit.config.network import (
    NetworkConfig,
    PopulationConfig,
    ScalingConfig,
    NeuronConfig,
    NeuronParams,
)
from human_microcircuit.utils.io import read_network_directory
from human_microcircuit.physiology.synaptic_parameters import (
    psp_to_psc,
)


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
        inputs={},
        scaling=ScalingConfig(
            N_scaling=0.5,
            K_scaling=1.0,
        ),
    )

    derived = ParameterBuilder(network).build()

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
        inputs={},
        scaling=ScalingConfig(
            N_scaling=1.0,
            K_scaling=0.5,
        ),
    )

    derived = ParameterBuilder(network).build()

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

    network_config = ConfigBuilder(network_files).build()

    derived = ParameterBuilder(network_config).build()

    expected = psp_to_psc(
        psp=0.15,
        C_m=250.0,
        tau_m=10.0,
        tau_syn=0.5,
    ) / math.sqrt(0.2)

    assert derived.connections[0].weight.mean == pytest.approx(expected)


def test_identity_scaling():

    network_files = read_network_directory("configs/network/pd14")

    network = ConfigBuilder(network_files).build()

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

    derived = ParameterBuilder(network).build()

    assert derived.populations["L23_E"].size == 20683

    assert derived.populations["L23_E"].background_indegree == 1600
