import numpy as np

from microcircuit_lab.network.compensation import (
    background_dc_current,
    network_compensation_current,
)


def test_network_compensation_current():

    network_input = np.array([2.0, 4.0])

    dc = network_compensation_current(
        network_input=network_input,
        tau_syn=0.5,
        K_scaling=4.0,
    )

    expected = 0.001 * 0.5 * (1.0 - np.sqrt(4.0)) * network_input

    assert np.allclose(dc, expected)


def test_background_dc_current():

    PSC_ext = np.array([50.0, 60.0])
    K_ext = np.array([1000.0, 1500.0])
    bg_rate = np.array([8.0, 8.0])
    tau_syn = np.array([0.5, 0.5])

    dc = background_dc_current(
        PSC_ext=PSC_ext,
        K_ext=K_ext,
        bg_rate=bg_rate,
        tau_syn=tau_syn,
    )

    expected = 0.001 * tau_syn * PSC_ext * K_ext * bg_rate

    assert np.allclose(dc, expected)
