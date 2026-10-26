"""
Quantities derived from a whole network, as matrices and vectors: indegrees,
mean weights, background input and so on.

Builders and the scaling steps use them. They do not change the network.
"""

from __future__ import annotations

import numpy as np

from microcircuit_lab.config.network import NetworkConfig


def full_num_neurons(network: NetworkConfig) -> np.ndarray:
    """
    Return the full neuron numbers as a vector.

    These correspond to the biological (unscaled) network.
    """

    return np.asarray(
        [pop.size for pop in network.populations.values()],
        dtype=float,
    )


def expected_synapses(rule, number, n_source, n_target):
    """
    The expected number of synapses of a connection, whatever its rule:

    ==================== ==============================
    rule                 expected synapses
    ==================== ==============================
    fixed_total_number   n_synapses
    fixed_indegree       indegree x n_target
    fixed_outdegree      outdegree x n_source
    pairwise_bernoulli   p x n_source x n_target
    one_to_one           n_target
    all_to_all           n_source x n_target
    ==================== ==============================

    ``number`` is the number the rule takes (NaN for a rule that takes none);
    every argument may be a single value or one value per connection. A
    project rule's count is not known here: NaN.
    """

    rule, number = np.asarray(rule), np.asarray(number, dtype=float)
    n_source, n_target = np.asarray(n_source, dtype=float), np.asarray(n_target, dtype=float)
    return np.select(
        [rule == "fixed_indegree", rule == "fixed_outdegree", rule == "pairwise_bernoulli",
         rule == "one_to_one", rule == "all_to_all"],
        [number * n_target, number * n_source, number * n_source * n_target,
         n_target * np.ones_like(number), n_source * n_target * np.ones_like(number)],
        default=number,
    )


def expected_synapses_per_connection(network: NetworkConfig) -> np.ndarray:
    """:func:`expected_synapses` of every connection of the network, one value per row."""

    table = network.connections
    names = list(network.populations)
    sizes = np.asarray([pop.size for pop in network.populations.values()], dtype=float)
    return expected_synapses(
        table["rule"],
        table["number"],
        n_source=sizes[table.population_index("source", names)],
        n_target=sizes[table.population_index("target", names)],
    )


def full_num_synapses(network: NetworkConfig) -> np.ndarray:
    """
    Return the full synapse numbers as a matrix (target x source).

    These correspond to the biological (unscaled) network. Each entry is the
    expected number of synapses of the pair, summed over its connections
    (several when a pair is connected through several synapses).
    """

    pop_names = list(network.populations.keys())
    n = len(pop_names)
    table = network.connections

    matrix = np.zeros((n, n), dtype=float)
    np.add.at(
        matrix,
        (table.population_index("target", pop_names), table.population_index("source", pop_names)),
        expected_synapses_per_connection(network),
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
            "population; add them to reference.yaml, or scale with compensate_recurrent_input "
            "false (background only) or preserve_mean_input false (no current)."
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
    Return the background input weights as given, 0 for a population without
    background input. The compensation uses only those in pA.
    """

    return np.asarray(
        [
            network.background_inputs[name].weight.mean if name in network.background_inputs else 0.0
            for name in network.populations
        ],
        dtype=float,
    )


def mean_psc_matrix(
    network: NetworkConfig,
) -> np.ndarray:
    """
    Return the mean weight matrix (target x source), weights as given; the
    compensation uses only those in pA. A pair connected through several
    synapses gets the mean over all its synapses.
    """

    pop_names = list(network.populations.keys())
    n = len(pop_names)
    table = network.connections

    weight = table["weight.mean"]
    synapses = expected_synapses_per_connection(network)
    pair = (table.population_index("target", pop_names), table.population_index("source", pop_names))

    def sum_per_pair(values):
        matrix = np.zeros((n, n))
        np.add.at(matrix, pair, values)
        return matrix

    # Most pairs have one connection: their weight as it is. A pair with
    # several (one per synapse model) gets the mean of their weights,
    # weighted by the expected synapses of each (the plain mean if none).
    connections = sum_per_pair(1.0)
    weights = sum_per_pair(weight)
    synapse_count = sum_per_pair(synapses)
    with np.errstate(invalid="ignore", divide="ignore"):
        several = np.where(
            synapse_count > 0, sum_per_pair(weight * synapses) / synapse_count, weights / connections
        )
    return np.select([connections == 1, connections > 1], [weights, several], default=0.0)


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

    Used by DC-current scaling compensation, which assumes current-based
    synapses with exponential currents.
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
    one (the weight's sign picks the receptor, as in NEST). A population
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
