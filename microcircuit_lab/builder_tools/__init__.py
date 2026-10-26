"""
Everything a builder needs, in one import.

A builder turns a model's data (published tables, pickles, recordings) into a
network folder ``configs/network/<name>/``::

    from microcircuit_lab.builder_tools import delay, weight, write_network_directory

    write_network_directory(
        "configs/network/my_model",
        populations=[{"name": "E", "size": 800, "neuron": "lif", ...}],
        neurons={"lif": {"model": "iaf_psc_exp", "parameters": {...}}},
        connections=[{"source": "E", "target": "E", "n_synapses": 8000,
                      "weight": weight(87.8, unit="pA", rel_std=0.1),
                      "delay": delay(1.5, rel_std=0.5)}],
        background_inputs={"E": {"rate": 8.0, "weight": weight(87.8, unit="pA"),
                                 "delay": delay(1.5)}},
    )

Modules: ``entries.py`` (weight, delay, synapses from a probability),
``write.py`` (network folders), ``psp.py`` (PSP to PSC), ``scaling.py`` (scale
a network) and ``constant_current.py`` / ``mean_input.py`` (the currents and
quantities it uses).

* :func:`write_network_directory` writes every file of the folder and checks
  the result (with :func:`microcircuit_lab.network.load.read_network`), so a
  mistake raises with the file and the field named.
* :func:`scale_network` returns a network scaled down (fewer neurons and
  synapses, stronger weights, the lost mean input as a current), and
  :func:`write_network` writes such a network as a folder.
* :func:`mean_current` is the constant current (pA) with the mean of a
  Poisson input, for a builder that adds the input of areas it leaves out.
* :func:`weight` and :func:`delay` build the ``weight`` / ``delay`` entries
  every connection, background input and stimulus needs.
* :func:`num_synapses_from_conn_prob` turns a connection probability into a
  number of synapses (Potjans & Diesmann 2014).
* :func:`psp_to_psc_iaf_psc_exp` converts a PSP amplitude (mV) into the
  current (pA) that produces it, for a model whose weights are given as PSPs
  (:func:`psc_to_psp` goes back). The core never converts a weight itself.

None of these invents model values: a field a builder leaves out is either a
default of the config models or an error. Using them is optional; files
written any other way are checked the same way when the network is loaded.
"""

from __future__ import annotations

from microcircuit_lab.builder_tools.constant_current import mean_current
from microcircuit_lab.builder_tools.entries import (
    delay,
    num_synapses_from_conn_prob,
    weight,
)
from microcircuit_lab.builder_tools.psp import psc_to_psp, psp_to_psc_iaf_psc_exp
from microcircuit_lab.builder_tools.scaling import scale_network
from microcircuit_lab.builder_tools.write import write_network, write_network_directory

__all__ = [
    "delay",
    "mean_current",
    "num_synapses_from_conn_prob",
    "psc_to_psp",
    "psp_to_psc_iaf_psc_exp",
    "scale_network",
    "weight",
    "write_network",
    "write_network_directory",
]
