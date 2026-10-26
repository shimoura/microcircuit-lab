import numpy as np

from microcircuit_lab.builder_tools.constant_current import mean_current


def test_mean_current():

    weight = np.array([50.0, 60.0])
    indegree = np.array([1000.0, 1500.0])
    rate = np.array([8.0, 8.0])
    tau_syn = np.array([0.5, 0.5])

    current = mean_current(weight, indegree, rate, tau_syn)

    assert np.allclose(current, 0.001 * tau_syn * weight * indegree * rate)
