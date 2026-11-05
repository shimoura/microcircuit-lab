"""Distributions of the project for NEST.

Every function in a file of this folder is a distribution that a weight, delay
or neuron value can name, when NEST has none of that name (``nest.random``). It
returns a NEST parameter and gets the keys of the entry it names, all of which
the entry gives:

    # extensions/nest/distributions.py
    import nest

    def erlang2(beta):
        return nest.random.exponential(beta=beta) + nest.random.exponential(beta=beta)

    # connectivity.yaml
    weight: {distribution: erlang2, beta: 20, mean: 40, unit: pA}

A name that starts with ``_`` is a helper, not a distribution.
"""
