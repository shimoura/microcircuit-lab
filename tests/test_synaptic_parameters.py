import numpy as np

from microcircuit_lab.reference_models.common.synapses import (
    psc_over_psp,
    psc_to_psp,
    psp_to_psc_iaf_psc_exp,
)


def test_roundtrip():

    psp = 0.15

    psc = psp_to_psc_iaf_psc_exp(
        psp=psp,
        C_m=250.0,
        tau_m=10.0,
        tau_syn=0.5,
    )

    recovered = psc_to_psp(
        psc=psc,
        C_m=250.0,
        tau_m=10.0,
        tau_syn=0.5,
    )

    assert np.isclose(psp, recovered)


def test_positive_conversion():

    factor = psc_over_psp(
        C_m=250.0,
        tau_m=10.0,
        tau_syn=0.5,
    )

    assert factor > 0.0


def test_reference_value():

    factor = psc_over_psp(
        C_m=250.0,
        tau_m=10.0,
        tau_syn=0.5,
    )

    assert np.isclose(
        factor,
        585.3899568613896,
    )

def test_known_conversion():

    psc = psp_to_psc_iaf_psc_exp(
        psp=0.15,
        C_m=250.0,
        tau_m=10.0,
        tau_syn=0.5,
    )

    assert abs(psc - 87.80849352920844) < 1e-12