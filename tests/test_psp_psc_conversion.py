"""The PSP-to-PSC formulas builders use, and the weight units of earlier
versions, which now fail with the form to write instead."""

import numpy as np
import pytest

from microcircuit_lab.builder_tools import (
    psc_to_psp,
    psp_to_psc_iaf_psc_exp,
)
from microcircuit_lab.config.connectivity import WeightDistribution
from microcircuit_lab.config.neurons import NeuronEntry


def test_psp_psc_roundtrip():
    psc = psp_to_psc_iaf_psc_exp(psp=0.15, C_m=250.0, tau_m=10.0, tau_syn=0.5)
    assert np.isclose(psc_to_psp(psc=psc, C_m=250.0, tau_m=10.0, tau_syn=0.5), 0.15)


def test_psp_to_psc_known_value():
    psc = psp_to_psc_iaf_psc_exp(psp=0.15, C_m=250.0, tau_m=10.0, tau_syn=0.5)
    assert abs(psc - 87.80849352920844) < 1e-12


@pytest.mark.parametrize(
    ("unit", "message"),
    [
        ("PSP", "convert the PSP in the builder"),
        ("PSC", "now written unit: pA"),
        ("native", "write the weight's unit, pA, nS or mV"),
    ],
)
def test_an_old_unit_fails_with_the_new_form(unit, message):
    with pytest.raises(ValueError, match=message):
        WeightDistribution(mean=0.15, rel_std=0.0, unit=unit)


def test_psp_conversion_aliases_fail_with_the_new_form():
    with pytest.raises(ValueError, match="psp_conversion_aliases was removed"):
        NeuronEntry(model="my_lif", parameters={"cm": 250.0}, psp_conversion_aliases={"C_m": "cm"})
