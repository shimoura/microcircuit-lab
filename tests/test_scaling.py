from human_microcircuit.physiology.common.scaling import (
    scale_neuron_number,
    scale_synapse_number,
    scale_weight,
    scale_weight_sqrt,
)


def test_scale_neurons():

    assert scale_neuron_number(1000, 0.5) == 500


def test_scale_synapses():

    assert scale_synapse_number(1000, 0.5) == 500


def test_scale_weight():

    assert scale_weight(80.0, 2.0) == 40.0


def test_scale_weight_sqrt():

    assert (
        scale_weight_sqrt(
            100.0,
            4.0,
        )
        == 50.0
    )
