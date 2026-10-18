"""
Utilities operating on complete network descriptions.

This module provides functions that derive matrices or vectors from a
NetworkConfig representation without modifying its underlying biological
meaning. These quantities are commonly used by builders and analytical
routines.

Typical examples include indegree matrices, background indegree vectors,
mean synaptic weight matrices, and other derived network-level
representations.
"""

from __future__ import annotations

import numpy as np

from microcircuit_lab.config.network import DcStimulusConfig, NetworkConfig, PopulationConfig
from microcircuit_lab.network.synapses import convert_psp_to_psc


def full_num_neurons(network: NetworkConfig) -> np.ndarray:
    """
    Return the full neuron numbers as a vector.

    These correspond to the biological (unscaled) network.
    """

    return np.asarray(
        [pop.size for pop in network.populations.values()],
        dtype=float,
    )


def full_num_synapses(network: NetworkConfig) -> np.ndarray:
    """
    Return the full synapse numbers as a matrix.

    These correspond to the biological (unscaled) network.
    """

    pop_names = list(network.populations.keys())
    n = len(pop_names)

    matrix = np.zeros((n, n), dtype=float)

    name_to_index = {name: i for i, name in enumerate(pop_names)}

    for connection in network.connections:

        i = name_to_index[connection.target]
        j = name_to_index[connection.source]

        matrix[i, j] = connection.n_synapses

    return matrix


def indegree_matrix(network: NetworkConfig) -> np.ndarray:
    """
    Return the biological indegree matrix.
    """

    neurons = full_num_neurons(network)
    synapses = full_num_synapses(network)

    return synapses / neurons[:, np.newaxis]


def full_mean_rates(network: NetworkConfig) -> np.ndarray:
    """
    Return the full mean firing rates as a vector.
    """

    if network.reference is None:
        raise ValueError(
            "NetworkConfig.reference is required to obtain " "reference firing rates."
        )

    return np.asarray(
        [network.reference.full_mean_rates[name] for name in network.populations],
        dtype=float,
    )


def background_indegrees(network: NetworkConfig) -> np.ndarray:
    return np.asarray(
        [pop.background_indegree for pop in network.populations.values()],
        dtype=float,
    )


def background_weights(network: NetworkConfig) -> np.ndarray:
    return np.asarray(
        [network.background_inputs[name].weight.mean for name in network.populations],
        dtype=float,
    )


def _convert_psp_weight(population: PopulationConfig, psp: float) -> float:
    """
    Convert one PSP-unit weight (mV) to PSC (pA) for `population`.

    Any error from convert_psp_to_psc() is re-raised with the population
    name added, so a failure points at which population caused it.
    """

    try:
        return convert_psp_to_psc(
            population.neuron.model,
            psp,
            population.neuron.parameters,
            aliases=population.neuron.psp_conversion_aliases,
        )
    except ValueError as exc:
        raise ValueError(f"Population {population.name!r}: {exc}") from exc


def background_psc_weights(
    network: NetworkConfig,
) -> np.ndarray:
    """
    Return the background input weights as PSC amplitudes (pA).

    Only ``unit: PSP`` weights are converted, and only for a population
    whose neuron parameters support it (see network.synapses.convert_psp_to_psc);
    any other unit (``PSC``, ``native``, ...) is returned unchanged.
    """

    values = []
    for name in network.populations:
        input_cfg = network.background_inputs[name]

        if input_cfg.weight.unit != "PSP":
            values.append(input_cfg.weight.mean)
            continue

        target = network.populations[name]
        values.append(_convert_psp_weight(target, input_cfg.weight.mean))

    return np.asarray(values, dtype=float)


def mean_psc_matrix(
    network: NetworkConfig,
) -> np.ndarray:
    """
    Return the biological mean PSC matrix (pA).

    Only ``unit: PSP`` connections are converted, and only for a target
    population whose neuron parameters support it (see
    network.synapses.convert_psp_to_psc); any other unit (``PSC``,
    ``native``, ...) is used unchanged.
    """

    pop_names = list(network.populations.keys())
    name_to_index = {name: i for i, name in enumerate(pop_names)}

    n = len(pop_names)

    matrix = np.zeros((n, n), dtype=float)

    for connection in network.connections:

        i = name_to_index[connection.target]
        j = name_to_index[connection.source]

        if connection.weight.unit != "PSP":
            matrix[i, j] = connection.weight.mean
            continue

        target = network.populations[connection.target]
        matrix[i, j] = _convert_psp_weight(target, connection.weight.mean)

    return matrix


def _tau_syn(network: NetworkConfig, parameter: str) -> np.ndarray:
    """Return neuron parameter ``parameter`` (a synaptic time constant) for
    each population. A population whose neuron parameters don't include it
    raises a clear error naming that population, instead of a bare
    AttributeError."""

    values = []
    for name, population in network.populations.items():
        try:
            values.append(population.neuron.parameters.require(parameter)[parameter])
        except KeyError as exc:
            raise ValueError(f"Population {name!r}: {exc.args[0]}") from exc

    return np.asarray(values, dtype=float)


def tau_syn_ex(
    network: NetworkConfig,
) -> np.ndarray:
    """
    Return the excitatory synaptic time constant for each population.

    Used by DC-current scaling compensation, which shares the same
    current-based-synapse assumption as the PSP-to-PSC conversion; see
    _convert_psp_weight.
    """

    return _tau_syn(network, "tau_syn_ex")


def tau_syn_in(
    network: NetworkConfig,
) -> np.ndarray:
    """Return the inhibitory synaptic time constant for each population."""

    return _tau_syn(network, "tau_syn_in")


def relative_tau_matrix(
    network: NetworkConfig,
    mean_PSC_matrix: np.ndarray,
) -> np.ndarray:
    """
    Return each connection's synaptic time constant relative to the
    excitatory one of its target: 1 for an excitatory connection (positive
    PSC), ``tau_syn_in / tau_syn_ex`` for an inhibitory one.

    DC-current scaling compensation multiplies the recurrent input by the
    target's ``tau_syn_ex``. Weighting the input by this matrix first gives
    every connection its own time constant, which is what the compensation
    needs when ``tau_syn_in`` differs from ``tau_syn_ex``. ``tau_syn_in`` is
    only read when the network has an inhibitory connection.
    """

    relative = np.ones_like(mean_PSC_matrix, dtype=float)
    inhibitory = mean_PSC_matrix < 0
    if inhibitory.any():
        ratio = tau_syn_in(network) / tau_syn_ex(network)
        relative = np.where(inhibitory, ratio[:, None], relative)

    return relative


def convert_network_psp_to_psc(
    network: NetworkConfig,
) -> NetworkConfig:
    """
    Convert synaptic weights stored as PSP amplitudes (``unit: PSP``) into
    PSC amplitudes. Any other unit (``PSC``, ``native``, ...) is left
    untouched; it is not reinterpreted as PSP.

    The conversion is performed independently for each target population
    using its neuron parameters, via network.synapses.convert_psp_to_psc;
    see that function for what it requires. A population whose neuron
    parameters don't support it raises ValueError; give its connections
    ``unit: native`` (or ``PSC`` if the weights are genuinely already
    current amplitudes in pA) instead.
    """

    connections = []
    for connection in network.connections:

        if connection.weight.unit != "PSP":
            connections.append(connection)
            continue

        target = network.populations[connection.target]

        weight = connection.weight.model_copy(
            update={
                "mean": _convert_psp_weight(target, connection.weight.mean),
                "unit": "PSC",
            }
        )

        connections.append(
            connection.model_copy(
                update={
                    "weight": weight,
                }
            )
        )

    background_inputs = {}
    for pop_name, input_cfg in network.background_inputs.items():

        if input_cfg.weight.unit != "PSP":
            background_inputs[pop_name] = input_cfg
            continue

        target = network.populations[pop_name]

        weight = input_cfg.weight.model_copy(
            update={
                "mean": _convert_psp_weight(target, input_cfg.weight.mean),
                "unit": "PSC",
            }
        )

        background_inputs[pop_name] = input_cfg.model_copy(
            update={
                "weight": weight,
            }
        )

    stimuli = []
    for stimulus in network.stimuli:

        if isinstance(stimulus, DcStimulusConfig) or stimulus.weight.unit != "PSP":
            stimuli.append(stimulus)
            continue

        # A stimulus has one weight shared across all its targets, so a PSP
        # amplitude only maps onto a single PSC amplitude if every target
        # converts it the same way. This is checked by converting for each
        # target and comparing the results, rather than by comparing which
        # neuron parameters happen to be involved.
        converted = {
            _convert_psp_weight(network.populations[t], stimulus.weight.mean)
            for t in stimulus.targets
        }
        if len(converted) > 1:
            raise ValueError(
                f"Cannot convert a unit: PSP stimulus weight shared across "
                f"targets {stimulus.targets!r}: those populations don't "
                "convert it to the same PSC amplitude. Split into separate "
                "stimuli (one per distinct neuron type), or give the weight "
                "as unit: PSC/native instead."
            )

        weight = stimulus.weight.model_copy(
            update={
                "mean": converted.pop(),
                "unit": "PSC",
            }
        )

        stimuli.append(
            stimulus.model_copy(
                update={
                    "weight": weight,
                }
            )
        )

    return network.model_copy(
        update={
            "connections": connections,
            "background_inputs": background_inputs,
            "stimuli": stimuli,
        }
    )


def network_mean_input(
    mean_PSC_matrix: np.ndarray,
    indegree_matrix: np.ndarray,
    mean_rates: np.ndarray,
) -> np.ndarray:
    """
    Compute the mean recurrent synaptic input used for DC compensation
    when scaling synaptic weights.

    Parameters
    ----------
    mean_PSC_matrix
        Matrix of mean PSC amplitudes (pA).

    indegree_matrix
        Matrix of indegrees.

    mean_rates
        Mean firing rate of each source population (Hz).

    Returns
    -------
    np.ndarray
        Mean recurrent input for each target population.
    """

    return np.sum(
        mean_PSC_matrix * indegree_matrix * mean_rates,
        axis=1,
    )
