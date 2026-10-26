"""
Prepare a network for the simulation: the steps between the network as
written in the files and the network the simulator builds.

The files hold the numbers that are simulated (a scaled network is written
scaled, see ``builder_tools/scaling.py``; a background replaced by its mean
current is written replaced, see ``builder_tools/constant_current.py``), so
only one step remains: :func:`prepare_network`.
"""

from __future__ import annotations

from microcircuit_lab.config.network import NetworkConfig


def prepare_network(config: NetworkConfig) -> NetworkConfig:
    """
    Return the network ready to simulate; ``config`` itself is not changed.

    The only step: turn each population's background rate per synapse into the
    rate of its Poisson generator (rate x indegree).

    Parameters
    ----------
    config
        The network as read from its files (see
        :func:`microcircuit_lab.network.load.read_network`).

    Returns
    -------
    NetworkConfig
        A new network description with the background rates per generator.
    """

    return _background_rate_per_neuron(config)


def _background_rate_per_neuron(
    network: NetworkConfig,
) -> NetworkConfig:
    """
    Convert biological background rates into effective
    Poisson generator rates.

    The effective rate is computed as the product of the background
    rate and the background indegree, i.e.,
        effective_rate = bg_rate * K_ext
    """

    background_inputs = {}

    for pop_name, input_cfg in network.background_inputs.items():
        K_ext = network.populations[pop_name].background_indegree

        background_inputs[pop_name] = input_cfg.model_copy(update={"rate": input_cfg.rate * K_ext})

    return network.model_copy(update={"background_inputs": background_inputs})
