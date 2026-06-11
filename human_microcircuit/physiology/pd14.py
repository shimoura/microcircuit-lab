"""
Mathematical functions reproducing the Potjans & Diesmann (2014)
microcircuit parameter derivation.

This module intentionally contains only pure functions.

No NEST code.
No Pydantic.
No file I/O.
No side effects.

Its purpose is to provide a mathematically validated reference
implementation that can later be used by ParameterBuilder.
"""

from __future__ import annotations

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
