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