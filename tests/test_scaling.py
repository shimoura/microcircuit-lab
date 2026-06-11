from human_microcircuit.physiology.scaling import (
    scale_neuron_number,
    scale_synapse_number,
    scale_weight,
)


def test_scale_neurons():

    assert scale_neuron_number(1000, 0.5) == 500


def test_scale_synapses():

    assert scale_synapse_number(1000, 0.5) == 500


def test_scale_weight():

    assert scale_weight(80.0, 2.0) == 40.0