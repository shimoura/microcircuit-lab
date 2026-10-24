"""Brian2 simulator backend.

``simulator.py`` builds and runs the network in Brian2; ``models.py`` finds the
neuron and synapse models of the project; ``distributions.py`` draws weights,
delays and per-neuron values; ``connections.py`` picks who connects to whom;
``spike_files.py`` reads a saved run back without importing Brian2, so a saved
run can be analysed without it. This file imports nothing, for that reason.
"""
