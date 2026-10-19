"""
Quantities derived from a whole network, as matrices and vectors: indegrees,
mean weights, background input and so on.

Builders and the scaling steps use them. They do not change the network.
"""

from __future__ import annotations

import numpy as np

from microcircuit_lab.config.connectivity import ConnectionConfig
from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.network.units import convert_psp_weight


def full_num_neurons(network: NetworkConfig) -> np.ndarray:
    """
    Return the full neuron numbers as a vector.

    These correspond to the biological (unscaled) network.
    """

    return np.asarray(
        [pop.size for pop in network.populations.values()],
        dtype=float,
    )


def expected_synapses(connection: ConnectionConfig, n_source: int, n_target: int) -> float:
    """The expected number of synapses of a connection between populations of
    these sizes, whatever its rule."""

    if connection.rule == "fixed_total_number":
        return float(connection.n_synapses)
    if connection.rule == "fixed_indegree":
        return float(connection.indegree * n_target)
    if connection.rule == "fixed_outdegree":
        return float(connection.outdegree * n_source)
    return connection.p * n_source * n_target


def full_num_synapses(network: NetworkConfig) -> np.ndarray:
    """
    Return the full synapse numbers as a matrix (target x source).

    These correspond to the biological (unscaled) network. Each entry is the
    expected number of synapses of the pair, summed over its connections
    (several when a pair is connected through several synapses).
    """

    pop_names = list(network.populations.keys())
    n = len(pop_names)

    matrix = np.zeros((n, n), dtype=float)

    name_to_index = {name: i for i, name in enumerate(pop_names)}

    for connection in network.connections:

        i = name_to_index[connection.target]
        j = name_to_index[connection.source]

        matrix[i, j] += expected_synapses(
            connection,
            network.populations[connection.source].size,
            network.populations[connection.target].size,
        )

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

    rates = {} if network.reference is None else network.reference.full_mean_rates
    missing = [name for name in network.populations if name not in rates]
    if missing:
        raise ValueError(
            f"reference.full_mean_rates has no rate for population(s) {missing}. The DC "
            "compensation of a scaled network needs the full-scale mean rate of every "
            "population; add them to reference.yaml, or set compensate_recurrent_input: "
            "false (background only) or preserve_mean_input: false (no DC) in scaling.yaml."
        )

    return np.asarray([rates[name] for name in network.populations], dtype=float)


def background_indegrees(network: NetworkConfig) -> np.ndarray:
    return np.asarray(
        [pop.background_indegree for pop in network.populations.values()],
        dtype=float,
    )


def background_weights(network: NetworkConfig) -> np.ndarray:
    """The background weight of each population, 0 for one without background input."""
    return np.asarray(
        [
            network.background_inputs[name].weight.mean if name in network.background_inputs else 0.0
            for name in network.populations
        ],
        dtype=float,
    )


def background_rates(network: NetworkConfig) -> np.ndarray:
    """The background rate per synapse of each population (spikes/s), 0 for one
    without background input."""
    return np.asarray(
        [
            network.background_inputs[name].rate if name in network.background_inputs else 0.0
            for name in network.populations
        ],
        dtype=float,
    )


def background_psc_weights(
    network: NetworkConfig,
) -> np.ndarray:
    """
    Return the background input weights as PSC amplitudes (pA), 0 for a
    population without background input.

    Only ``unit: PSP`` weights are converted, and only for a population
    whose neuron parameters support it (see network.units.convert_psp_to_psc);
    any other unit (``PSC``, ``native``, ...) is returned unchanged.
    """

    values = []
    for name in network.populations:
        input_cfg = network.background_inputs.get(name)

        if input_cfg is None:
            values.append(0.0)
            continue
        if input_cfg.weight.unit != "PSP":
            values.append(input_cfg.weight.mean)
            continue

        target = network.populations[name]
        values.append(convert_psp_weight(target, input_cfg.weight.mean))

    return np.asarray(values, dtype=float)


def mean_psc_matrix(
    network: NetworkConfig,
) -> np.ndarray:
    """
    Return the biological mean PSC matrix (pA, target x source).

    Only ``unit: PSP`` connections are converted, and only for a target
    population whose neuron parameters support it (see
    network.units.convert_psp_to_psc); any other unit (``PSC``,
    ``native``, ...) is used unchanged. A pair connected through several
    synapses gets the mean over all its synapses.
    """

    pop_names = list(network.populations.keys())
    name_to_index = {name: i for i, name in enumerate(pop_names)}

    n = len(pop_names)

    # (weight, expected number of synapses) of each connection, per pair
    entries: dict[tuple[int, int], list[tuple[float, float]]] = {}

    for connection in network.connections:

        i = name_to_index[connection.target]
        j = name_to_index[connection.source]

        weight = connection.weight.mean
        if connection.weight.unit == "PSP":
            weight = convert_psp_weight(network.populations[connection.target], weight)

        count = expected_synapses(
            connection,
            network.populations[connection.source].size,
            network.populations[connection.target].size,
        )
        entries.setdefault((i, j), []).append((weight, count))

    matrix = np.zeros((n, n), dtype=float)
    for (i, j), pair in entries.items():
        weights, counts = zip(*pair)
        if len(pair) == 1:
            matrix[i, j] = weights[0]
        else:
            matrix[i, j] = np.average(weights, weights=counts if sum(counts) else None)

    return matrix


def _tau_syn(network: NetworkConfig, parameter: str, needed=None) -> np.ndarray:
    """Return neuron parameter ``parameter`` (a synaptic time constant) for
    each population. A population whose neuron parameters don't include it
    raises a clear error naming that population, instead of a bare
    AttributeError. With ``needed`` (one bool per population), the others
    get 0 and are not read: a neuron with only other receptor ports has no
    ``tau_syn_ex``."""

    values = []
    for index, (name, population) in enumerate(network.populations.items()):
        if needed is not None and not needed[index]:
            values.append(0.0)
            continue
        try:
            values.append(population.neuron.parameters.require(parameter)[parameter])
        except KeyError as exc:
            raise ValueError(f"Population {name!r}: {exc.args[0]}") from exc

    return np.asarray(values, dtype=float)


def tau_syn_ex(
    network: NetworkConfig,
    needed=None,
) -> np.ndarray:
    """
    Return the excitatory synaptic time constant for each population
    (only for those ``needed``, if given; 0 for the others).

    Used by DC-current scaling compensation, which shares the same
    current-based-synapse assumption as the PSP-to-PSC conversion; see
    convert_psp_weight.
    """

    return _tau_syn(network, "tau_syn_ex", needed)


def tau_syn_in(
    network: NetworkConfig,
    needed=None,
) -> np.ndarray:
    """Return the inhibitory synaptic time constant for each population
    (only for those ``needed``, if given; 0 for the others)."""

    return _tau_syn(network, "tau_syn_in", needed)


def synaptic_tau(
    network: NetworkConfig,
    mean_PSC: np.ndarray,
) -> np.ndarray:
    """
    Return the synaptic time constant (ms) of the input of each population,
    given its mean PSC (one value per population): the population's
    ``tau_syn_ex`` for a positive PSC and its ``tau_syn_in`` for a negative
    one, the same sign rule the PSP-to-PSC conversion uses. A population
    without input (PSC 0) gets 0, and its time constants are not read.
    """

    excitatory = tau_syn_ex(network, needed=mean_PSC > 0)
    inhibitory = tau_syn_in(network, needed=mean_PSC < 0)
    return np.where(mean_PSC < 0, inhibitory, excitatory)


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
