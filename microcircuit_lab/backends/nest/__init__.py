"""NEST simulator backend.

``backend.py`` builds and runs the network in NEST; ``distributions.py`` draws its
weights, delays and per-neuron values; ``spike_files.py`` reads NEST's spike files back
without importing NEST, so a saved run can be analysed without it. This file
imports nothing, for that reason.
"""
