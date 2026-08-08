"""Tests for weight.unit handling in PSP/PSC conversion.

Covers three call sites that each independently need to respect
weight.unit and require the target neuron to have the parameters
convert_psp_to_psc needs (C_m, tau_m, tau_syn_ex, tau_syn_in): the main
convert_network_psp_to_psc pass (runs for every network), and
mean_psc_matrix/background_psc_weights (used by the scaling-compensation
DC-current calculation, which runs whenever a network is scaled --
including PD14's bundled default, N_scaling/K_scaling: 0.05).

The conversion doesn't look at the neuron's `model` name at all, only at
which parameters are present -- see network.synapses.convert_psp_to_psc.
CONDUCTANCE_NEURON_PARAMS stands in for a real conductance-based model
(no tau_m; a leak conductance g_L instead, matching e.g. NEST's
aeif_cond_exp/iaf_cond_exp/iaf_cond_alpha) to exercise that missing-parameter
path realistically.
"""

import pytest

from microcircuit_lab.config.network import (
    BackgroundInputConfig,
    ConnectionConfig,
    DelayDistribution,
    NetworkConfig,
    NeuronConfig,
    NeuronParams,
    PopulationConfig,
    ReferenceConfig,
    ScalingConfig,
    WeightDistribution,
)
from microcircuit_lab.network.parameters import (
    convert_network_psp_to_psc,
    background_psc_weights,
    mean_psc_matrix,
)
from microcircuit_lab.network.preprocessing import NetworkPreprocessor

NEURON_PARAMS = NeuronParams(
    C_m=250.0,
    tau_m=10.0,
    tau_syn_ex=0.5,
    tau_syn_in=0.5,
    E_L=-65.0,
    V_reset=-65.0,
    V_th=-50.0,
    t_ref=2.0,
)

CONDUCTANCE_NEURON_PARAMS = NeuronParams(
    C_m=250.0,
    g_L=16.6,
    tau_syn_ex=0.5,
    tau_syn_in=0.5,
    E_L=-65.0,
    E_ex=0.0,
    E_in=-85.0,
    V_reset=-65.0,
    V_th=-50.0,
    t_ref=2.0,
)

# Same physical neuron as NEURON_PARAMS (C_m=250.0, tau_m=10.0,
# tau_syn_ex/in=0.5), but under a NESTML-style naming convention, to
# exercise NeuronConfig.psp_conversion_aliases.
NESTML_STYLE_NEURON_PARAMS = NeuronParams(
    Cm=250.0,
    tau_membrane=10.0,
    tau_exc=0.5,
    tau_inh=0.5,
    E_L=-65.0,
    V_reset=-65.0,
    V_th=-50.0,
    t_ref=2.0,
)

NESTML_STYLE_ALIASES = {
    "C_m": "Cm",
    "tau_m": "tau_membrane",
    "tau_syn_ex": "tau_exc",
    "tau_syn_in": "tau_inh",
}


def _network(
    *,
    neuron_model: str,
    weight_unit: str,
    neuron_params: NeuronParams = NEURON_PARAMS,
    psp_conversion_aliases: dict[str, str] | None = None,
    scaling: ScalingConfig | None = None,
    with_reference: bool = False,
) -> NetworkConfig:
    neuron = NeuronConfig(
        name="E",
        model=neuron_model,
        parameters=neuron_params,
        psp_conversion_aliases=psp_conversion_aliases or {},
    )
    population = PopulationConfig(
        name="E", size=10, neuron=neuron, V0_mean=-65.0, V0_std=5.0,
        background_indegree=100,
    )
    weight = WeightDistribution(mean=0.15, rel_std=0.1, unit=weight_unit)
    delay = DelayDistribution(mean=1.5, rel_std=0.5)

    return NetworkConfig(
        populations={"E": population},
        connections=[
            ConnectionConfig(source="E", target="E", n_synapses=100, weight=weight, delay=delay)
        ],
        background_inputs={"E": BackgroundInputConfig(rate=8.0, weight=weight, delay=delay)},
        scaling=scaling or ScalingConfig(),
        reference=ReferenceConfig(full_mean_rates={"E": 5.0}) if with_reference else None,
    )


def test_psc_unit_weights_are_left_untouched():
    network = _network(neuron_model="iaf_psc_exp", weight_unit="PSC")

    converted = convert_network_psp_to_psc(network)

    assert converted.connections[0].weight.mean == 0.15
    assert converted.connections[0].weight.unit == "PSC"
    assert converted.background_inputs["E"].weight.mean == 0.15


def test_psp_unit_weights_are_converted():
    network = _network(neuron_model="iaf_psc_exp", weight_unit="PSP")

    converted = convert_network_psp_to_psc(network)

    assert converted.connections[0].weight.unit == "PSC"
    assert converted.connections[0].weight.mean != 0.15
    assert converted.connections[0].weight.mean == pytest.approx(87.80849352920844)


def test_psp_conversion_supports_a_renamed_model_via_aliases():
    """A NESTML-style model whose parameters aren't literally named
    C_m/tau_m/tau_syn_ex/tau_syn_in still converts correctly once its
    NeuronConfig declares psp_conversion_aliases, and produces the exact
    same PSC value as the canonically-named model with the same physical
    parameters (see test_psp_unit_weights_are_converted)."""

    network = _network(
        neuron_model="my_nestml_lif_exp",
        weight_unit="PSP",
        neuron_params=NESTML_STYLE_NEURON_PARAMS,
        psp_conversion_aliases=NESTML_STYLE_ALIASES,
    )

    converted = convert_network_psp_to_psc(network)

    assert converted.connections[0].weight.mean == pytest.approx(87.80849352920844)


def test_psp_conversion_missing_aliased_parameter_names_the_aliased_key():
    """When a parameter is missing under its aliased name, the error
    should name what's actually missing from the config (the alias
    target), not the canonical name the user never wrote."""

    incomplete = NeuronParams(Cm=250.0, tau_exc=0.5, tau_inh=0.5)  # tau_membrane missing

    network = _network(
        neuron_model="my_nestml_lif_exp",
        weight_unit="PSP",
        neuron_params=incomplete,
        psp_conversion_aliases=NESTML_STYLE_ALIASES,
    )

    with pytest.raises(ValueError, match="tau_membrane"):
        convert_network_psp_to_psc(network)


def test_psp_conversion_on_neuron_missing_required_parameters_raises_useful_error():
    network = _network(
        neuron_model="aeif_cond_exp", weight_unit="PSP", neuron_params=CONDUCTANCE_NEURON_PARAMS,
    )

    with pytest.raises(ValueError, match="tau_m"):
        convert_network_psp_to_psc(network)


def test_psc_unit_skips_the_required_parameters_check():
    """A PSC-unit weight needs no conversion, so it shouldn't matter that
    the neuron's parameters don't support one."""

    network = _network(
        neuron_model="aeif_cond_exp", weight_unit="PSC", neuron_params=CONDUCTANCE_NEURON_PARAMS,
    )

    converted = convert_network_psp_to_psc(network)

    assert converted.connections[0].weight.mean == 0.15


# mean_psc_matrix / background_psc_weights: used by the scaling-compensation
# DC-current calculation (preprocessing.py::_apply_scaling_compensation),
# which is a *separate* call site from convert_network_psp_to_psc and
# needs its own unit.PSC / required-parameters guard.


def test_mean_psc_matrix_leaves_psc_unit_untouched():
    network = _network(neuron_model="iaf_psc_exp", weight_unit="PSC")

    assert mean_psc_matrix(network)[0, 0] == 0.15


def test_mean_psc_matrix_converts_psp_unit():
    network = _network(neuron_model="iaf_psc_exp", weight_unit="PSP")

    assert mean_psc_matrix(network)[0, 0] == pytest.approx(87.80849352920844)


def test_mean_psc_matrix_rejects_missing_required_parameters_for_psp_unit():
    network = _network(
        neuron_model="aeif_cond_exp", weight_unit="PSP", neuron_params=CONDUCTANCE_NEURON_PARAMS,
    )

    with pytest.raises(ValueError, match="tau_m"):
        mean_psc_matrix(network)


def test_background_psc_weights_leaves_psc_unit_untouched():
    network = _network(neuron_model="iaf_psc_exp", weight_unit="PSC")

    assert background_psc_weights(network)[0] == 0.15


def test_background_psc_weights_rejects_missing_required_parameters_for_psp_unit():
    network = _network(
        neuron_model="aeif_cond_exp", weight_unit="PSP", neuron_params=CONDUCTANCE_NEURON_PARAMS,
    )

    with pytest.raises(ValueError, match="tau_m"):
        background_psc_weights(network)


def test_psc_and_equivalent_psp_unit_networks_process_identically():
    """End-to-end regression covering NetworkPreprocessor.process(), which
    scales and applies DC compensation (PD14's bundled default scaling
    triggers this same path). A PSC-unit weight of X pA and a PSP-unit
    weight that converts to exactly X pA describe the same physical
    synapse, so they must produce identical results -- including the
    compensation current, which is where a silent PSC->PSP
    misinterpretation would previously have gone unnoticed (it doesn't
    show up in weight.mean, only in the compensation I_e)."""

    psc_value = 87.80849352920844  # == psp_to_psc_iaf_psc_exp(psp=0.15, ...)
    scaling = ScalingConfig(N_scaling=0.5, K_scaling=0.5)

    network_psc = _network(
        neuron_model="iaf_psc_exp", weight_unit="PSC", scaling=scaling, with_reference=True,
    )
    network_psc = network_psc.model_copy(
        update={
            "connections": [
                c.model_copy(update={"weight": c.weight.model_copy(update={"mean": psc_value})})
                for c in network_psc.connections
            ],
            "background_inputs": {
                name: cfg.model_copy(update={"weight": cfg.weight.model_copy(update={"mean": psc_value})})
                for name, cfg in network_psc.background_inputs.items()
            },
        }
    )
    network_psp = _network(
        neuron_model="iaf_psc_exp", weight_unit="PSP", scaling=scaling, with_reference=True,
    )  # mean=0.15 PSP, which converts to psc_value

    processed_psc = NetworkPreprocessor(network_psc).process()
    processed_psp = NetworkPreprocessor(network_psp).process()

    assert processed_psc.connections[0].weight.mean == pytest.approx(
        processed_psp.connections[0].weight.mean
    )
    assert processed_psc.populations["E"].neuron.parameters.I_e == pytest.approx(
        processed_psp.populations["E"].neuron.parameters.I_e
    )


# unit: "native" -- the general escape hatch for models with no PSP/PSC
# conversion formula (e.g. conductance-based). Must behave exactly like
# "PSC": pass-through, and no requirement on the neuron model at all.


def test_native_unit_is_left_untouched_by_conversion():
    network = _network(neuron_model="iaf_cond_exp", weight_unit="native")

    converted = convert_network_psp_to_psc(network)

    assert converted.connections[0].weight.mean == 0.15
    assert converted.connections[0].weight.unit == "native"
    assert converted.background_inputs["E"].weight.mean == 0.15


def test_native_unit_skips_neuron_model_check_everywhere():
    network = _network(neuron_model="iaf_cond_exp", weight_unit="native")

    assert convert_network_psp_to_psc(network).connections[0].weight.mean == 0.15
    assert mean_psc_matrix(network)[0, 0] == 0.15
    assert background_psc_weights(network)[0] == 0.15
