"""
Utilities related to network connectivity.

This module provides graph-level operations and transformations
that describe how neuronal populations are connected, independent
of the underlying synaptic dynamics or a particular reference model.

Typical examples include conversions between connection probabilities
and numbers of synapses, as well as the construction of indegree or
connectivity matrices from a network description.
"""

import numpy as np

def num_synapses_from_conn_prob(
    conn_prob: float,
    n_source: int,
    n_target: int,
) -> int:
    """
    Compute the total number of synapses from a connection probability.

    Parameters
    ----------
    conn_prob
        Connection probability.

    n_source
        Number of source neurons.

    n_target
        Number of target neurons.

    Returns
    -------
    int
        Expected total number of synapses.
    """

    if conn_prob <= 0.0:
        return 0

    prod = n_source * n_target

    num_syn = np.log(1.0 - conn_prob) / np.log((prod - 1.0) / prod)

    return int(round(num_syn))
