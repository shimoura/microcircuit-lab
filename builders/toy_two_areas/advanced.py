"""The two-area toy with the optional features of the config files turned on.

Writes ``configs/network/toy_two_areas_advanced/``: the areas, populations,
neuron entries and connection probabilities of ``toy_two_areas`` (see
``build.py``), with these changes:

* **Values drawn per neuron:** every neuron's threshold ``V_th`` (normal,
  around its entry's value) and its starting ``V_m`` (uniform between
  ``V_reset`` and ``V_th``).
* **Connection rules:** within an area, ``pairwise_bernoulli`` with the
  connection probability itself, and no neuron connected to itself; between
  areas, ``fixed_indegree``.
* **Synapse models:** the connections between areas use a depressing synapse
  (``tsodyks2_synapse``), with lognormal delays.
* **Receptor ports:** ``B__L23_E`` gets a neuron with three ports, one per kind
  of input (excitatory, inhibitory, from the other area), each with its own
  time constant. Its weights are written in pA (``unit: PSC``): the core
  converts PSP weights only for the default port.

The rates differ from ``toy_two_areas``. No ``scaling.yaml`` is written (it
runs at full scale) and no reference rates, so a scaled copy of this network
is not compensated.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from builders.toy_two_areas import data
from builders.toy_two_areas.build import (
    build_background_inputs,
    build_neurons,
    build_populations,
    connection_probability,
    delay_mean,
    population_name,
)
from microcircuit_lab.builder_tools import delay, psp_to_psc_iaf_psc_exp, weight, write_network_directory
from microcircuit_lab.config.network import NetworkConfig

# The synapse of each kind of input to data.RECEPTOR_PORT_POPULATION (see synapses()).
SYNAPSE_OF_PORT = {
    "excitatory": "excitatory_port",
    "inhibitory": "inhibitory_port",
    "other_area": "depressing_slow_port",
}


def synapses() -> dict[str, dict[str, Any]]:
    """The entries of synapses.yaml."""
    ports = data.RECEPTOR_PORTS
    return {
        # Input to the population with receptor ports: one synapse per port.
        "excitatory_port": {"model": "static_synapse", "receptor_port": ports["excitatory"]},
        "inhibitory_port": {"model": "static_synapse", "receptor_port": ports["inhibitory"]},
        "depressing_slow_port": {
            "model": "tsodyks2_synapse",
            "parameters": dict(data.DEPRESSING_SYNAPSE),
            "receptor_port": ports["other_area"],
        },
        # Input from the other area to every other population: default port.
        "depressing": {"model": "tsodyks2_synapse", "parameters": dict(data.DEPRESSING_SYNAPSE)},
    }


def neurons() -> dict[str, dict[str, Any]]:
    """The neuron entries of toy_two_areas, with each neuron's threshold drawn,
    and the receptor-port neuron for data.RECEPTOR_PORT_NEURON."""
    entries = build_neurons()

    for entry in entries.values():
        threshold = entry["parameters"]["V_th"]
        entry["parameters"]["V_th"] = {"distribution": "normal", "mean": threshold, "std": data.V_TH_STD}

    # One synaptic time constant per port, instead of tau_syn_ex and tau_syn_in.
    receptor_port_neuron = entries[data.RECEPTOR_PORT_NEURON]
    receptor_port_neuron["model"] = data.RECEPTOR_PORT_MODEL
    parameters = receptor_port_neuron["parameters"]
    del parameters["tau_syn_ex"], parameters["tau_syn_in"]
    parameters["tau_syn"] = list(data.RECEPTOR_PORT_TAU_SYN.values())

    return entries


def populations() -> list[dict[str, Any]]:
    """The populations of toy_two_areas, each neuron starting at a voltage
    drawn uniformly between its reset and its mean threshold."""
    entries = neurons()
    rows = build_populations()

    for row in rows:
        parameters = entries[row["neuron"]]["parameters"]
        row["initial_state"] = {
            "V_m": {
                "distribution": "uniform",
                "min": parameters["V_reset"],
                "max": parameters["V_th"]["mean"],
            }
        }

    return rows


def weight_onto_port(psp: float, port: str, rel_std: float = 0.0) -> dict[str, Any]:
    """A weight onto data.RECEPTOR_PORT_POPULATION, converted here from a PSP
    (mV) to a current (pA) with the time constant of that port."""
    parameters = {**data.BASE_NEURON, **data.NEURONS[data.RECEPTOR_PORT_NEURON]}
    current = psp_to_psc_iaf_psc_exp(
        psp,
        C_m=parameters["C_m"],
        tau_m=parameters["tau_m"],
        tau_syn=data.RECEPTOR_PORT_TAU_SYN[port],
    )
    return weight(current, unit="PSC", rel_std=rel_std)


def connections() -> list[dict[str, Any]]:
    """The connections of toy_two_areas, with a rule for each and the
    synapses above."""
    rows: list[dict[str, Any]] = []

    for target in data.POPULATIONS:
        for source in data.POPULATIONS:
            probability = connection_probability(source, target)
            if probability == 0.0:
                continue

            source_name = population_name(*source[:3])
            target_name = population_name(*target[:3])
            from_other_area = source[0] != target[0]
            psp = data.PSP[source[2]]
            row: dict[str, Any] = {"source": source_name, "target": target_name}

            if from_other_area:
                source_size = source[3]
                row["rule"] = "fixed_indegree"
                row["indegree"] = round(probability * source_size)
                row["synapse"] = "depressing"
                delay_distribution = "lognormal"
            else:
                row["rule"] = "pairwise_bernoulli"
                row["p"] = probability
                if source_name == target_name:
                    row["allow_autapses"] = False
                delay_distribution = "normal"

            if target_name == data.RECEPTOR_PORT_POPULATION:
                if from_other_area:
                    port = "other_area"
                else:
                    port = "excitatory" if psp > 0 else "inhibitory"
                row["synapse"] = SYNAPSE_OF_PORT[port]
                row["weight"] = weight_onto_port(psp, port, rel_std=data.WEIGHT_REL_STD)
            else:
                row["weight"] = weight(psp, unit="PSP", rel_std=data.WEIGHT_REL_STD)

            row["delay"] = delay(
                delay_mean(source, target),
                rel_std=data.DELAY_REL_STD,
                distribution=delay_distribution,
            )
            rows.append(row)

    return rows


def background_inputs() -> dict[str, dict[str, Any]]:
    """The background input of toy_two_areas. A neuron with receptor ports has
    no default port, so its background input names the excitatory one."""
    inputs = build_background_inputs()
    receptor_port_input = inputs[data.RECEPTOR_PORT_POPULATION]
    receptor_port_input["synapse"] = SYNAPSE_OF_PORT["excitatory"]
    receptor_port_input["weight"] = weight_onto_port(data.BG_PSP, "excitatory")
    return inputs


def generate_toy_two_areas_advanced(
    *,
    config_dir: str | Path = "configs",
    network_name: str = "toy_two_areas_advanced",
) -> NetworkConfig:
    """Write ``<config_dir>/network/<network_name>/`` and validate it."""

    return write_network_directory(
        Path(config_dir) / "network" / network_name,
        populations=populations(),
        neurons=neurons(),
        synapses=synapses(),
        connections=connections(),
        background_inputs=background_inputs(),
        compact=False,
    )
