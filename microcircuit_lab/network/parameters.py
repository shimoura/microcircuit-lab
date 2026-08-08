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

from microcircuit_lab.config.network import DcStimulusConfig, NetworkConfig
from microcircuit_lab.network.synapses import (
    psp_to_psc_iaf_psc_exp,
)


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


def _stimulus_conversion_params(
    network: NetworkConfig,
    targets: list[str],
) -> tuple[str, float, float, float, float]:
    """
    Return the (model, C_m, tau_m, tau_syn_ex, tau_syn_in) shared by every
    target population of a stimulus, raising if they don't actually agree.

    A stimulus has one weight shared across all its targets, so a PSP
    amplitude only maps onto a single PSC amplitude if every target would
    convert it the same way.
    """

    params = {
        (
            network.populations[t].neuron.model,
            network.populations[t].neuron.parameters.C_m,
            network.populations[t].neuron.parameters.tau_m,
            network.populations[t].neuron.parameters.tau_syn_ex,
            network.populations[t].neuron.parameters.tau_syn_in,
        )
        for t in targets
    }

    if len(params) > 1:
        raise ValueError(
            f"Cannot convert a unit: PSP stimulus weight shared across targets "
            f"{targets!r}: those populations don't all use the same neuron "
            "model/parameters, so one PSP amplitude wouldn't map to one PSC "
            "amplitude for all of them. Split into separate stimuli (one per "
            "distinct neuron type), or give the weight as unit: PSC/native instead."
        )

    return next(iter(params))


def _require_iaf_psc_exp(target, population_name: str) -> None:
    if target.neuron.model != "iaf_psc_exp":
        raise NotImplementedError(
            "PSP-to-PSC weight conversion is only implemented for "
            f"'iaf_psc_exp' neurons, but population {population_name!r} "
            f"uses {target.neuron.model!r}. Either use iaf_psc_exp, or "
            "supply this weight with unit: PSC (already a current "
            "amplitude in pA) or unit: native (used exactly as given, "
            "e.g. for a conductance-based model) instead."
        )


def background_psc_weights(
    network: NetworkConfig,
) -> np.ndarray:
    """
    Return the background input weights as PSC amplitudes (pA).

    Only ``unit: PSP`` weights are converted (``iaf_psc_exp`` neurons
    only); any other unit (``PSC``, ``native``, ...) is returned unchanged.
    """

    values = []
    for name in network.populations:
        input_cfg = network.background_inputs[name]

        if input_cfg.weight.unit != "PSP":
            values.append(input_cfg.weight.mean)
            continue

        target = network.populations[name]
        _require_iaf_psc_exp(target, name)

        values.append(
            psp_to_psc_iaf_psc_exp(
                psp=input_cfg.weight.mean,
                C_m=target.neuron.parameters.C_m,
                tau_m=target.neuron.parameters.tau_m,
                tau_syn=target.neuron.parameters.tau_syn_ex,
            )
        )

    return np.asarray(values, dtype=float)


def mean_psc_matrix(
    network: NetworkConfig,
) -> np.ndarray:
    """
    Return the biological mean PSC matrix (pA).

    Only ``unit: PSP`` connections are converted (``iaf_psc_exp`` neurons
    only); any other unit (``PSC``, ``native``, ...) is used unchanged.
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
        _require_iaf_psc_exp(target, connection.target)

        if connection.weight.mean >= 0:
            tau_syn = target.neuron.parameters.tau_syn_ex
        else:
            tau_syn = target.neuron.parameters.tau_syn_in

        matrix[i, j] = psp_to_psc_iaf_psc_exp(
            psp=connection.weight.mean,
            C_m=target.neuron.parameters.C_m,
            tau_m=target.neuron.parameters.tau_m,
            tau_syn=tau_syn,
        )

    return matrix


def tau_syn_ex(
    network: NetworkConfig,
) -> np.ndarray:
    """
    Return the excitatory synaptic time constant for each population.
    """

    return np.asarray(
        [
            network.populations[name].neuron.parameters.tau_syn_ex
            for name in network.populations
        ],
        dtype=float,
    )


def convert_network_psp_to_psc(
    network: NetworkConfig,
) -> NetworkConfig:
    """
    Convert synaptic weights stored as PSP amplitudes (``unit: PSP``) into
    PSC amplitudes. Any other unit (``PSC``, ``native``, ...) is left
    untouched -- it is not reinterpreted as PSP.

    The conversion is performed independently for each target
    population using its neuron parameters.

    Currently this transformation is only implemented for
    current-based leaky integrate-and-fire neurons with
    exponential synaptic currents (`iaf_psc_exp`). A new neuron model
    should not need a new conversion formula here: give its connections
    ``unit: native`` (or ``PSC`` if the weights are genuinely already
    current amplitudes in pA) instead.
    """

    connections = []
    for connection in network.connections:

        if connection.weight.unit != "PSP":
            connections.append(connection)
            continue

        target = network.populations[connection.target]
        _require_iaf_psc_exp(target, connection.target)

        if connection.weight.mean >= 0:
            tau_syn = target.neuron.parameters.tau_syn_ex
        else:
            tau_syn = target.neuron.parameters.tau_syn_in

        weight = connection.weight.model_copy(
            update={
                "mean": psp_to_psc_iaf_psc_exp(
                    psp=connection.weight.mean,
                    C_m=target.neuron.parameters.C_m,
                    tau_m=target.neuron.parameters.tau_m,
                    tau_syn=tau_syn,
                ),
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
        _require_iaf_psc_exp(target, pop_name)
        tau_syn = target.neuron.parameters.tau_syn_ex

        weight = input_cfg.weight.model_copy(
            update={
                "mean": psp_to_psc_iaf_psc_exp(
                    psp=input_cfg.weight.mean,
                    C_m=target.neuron.parameters.C_m,
                    tau_m=target.neuron.parameters.tau_m,
                    tau_syn=tau_syn,
                ),
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

        _, C_m, tau_m, tau_syn_ex, tau_syn_in = _stimulus_conversion_params(
            network, stimulus.targets
        )
        _require_iaf_psc_exp(network.populations[stimulus.targets[0]], stimulus.targets[0])

        tau_syn = tau_syn_ex if stimulus.weight.mean >= 0 else tau_syn_in

        weight = stimulus.weight.model_copy(
            update={
                "mean": psp_to_psc_iaf_psc_exp(
                    psp=stimulus.weight.mean,
                    C_m=C_m,
                    tau_m=tau_m,
                    tau_syn=tau_syn,
                ),
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
