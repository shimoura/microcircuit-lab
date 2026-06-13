import math

import pytest

from human_microcircuit.builders.parameter_builder import (
    ParameterBuilder,
)
from human_microcircuit.builders.config_builder import ConfigBuilder
from human_microcircuit.reference_models.common.synapses import psp_to_psc_iaf_psc_exp
from human_microcircuit.reference_models.common.connectivity import (
    num_synapses_from_conn_prob,
)
from human_microcircuit.utils.io import read_network_directory


def test_zero_connection_probability():

    assert (
        num_synapses_from_conn_prob(
            conn_prob=0.0,
            n_source=100,
            n_target=200,
        )
        == 0
    )


def test_positive_connection_probability():

    n = num_synapses_from_conn_prob(
        conn_prob=0.1,
        n_source=1000,
        n_target=500,
    )

    assert n > 0


def test_pd14_parameter_builder():

    network_files = read_network_directory("configs/network/pd14")

    network = ConfigBuilder(network_files).build()

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

    network = ParameterBuilder(network).build()

    assert network.populations["L23_E"].size == round(20683 * 0.2)

    assert network.populations["L23_I"].size == round(5834 * 0.2)

    assert network.inputs["L23_E"].rate == pytest.approx(8.0 * 1600 * 0.2)

    assert network.inputs["L23_E"].rate == 8.0 * 1600 * 0.2

    assert network.populations["L23_E"].background_indegree == pytest.approx(1600 * 0.2)


def test_pd14_first_weight():

    network_files = read_network_directory("configs/network/pd14")

    network = ConfigBuilder(network_files).build()

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

    network = ParameterBuilder(network).build()

    expected = psp_to_psc_iaf_psc_exp(
        psp=0.15,
        C_m=250.0,
        tau_m=10.0,
        tau_syn=0.5,
    ) / math.sqrt(0.2)

    assert network.connections[0].weight.mean == pytest.approx(expected)
