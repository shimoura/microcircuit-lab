"""
Parameter derivation.

This module derives simulator-ready parameters from the biological
network description while preserving the original immutable
configuration.
"""

from __future__ import annotations

import numpy as np

from human_microcircuit.config.network import (
    NetworkConfig,
)

from human_microcircuit.physiology.scaling import (
    scale_neuron_number,
    scale_synapse_number,
    scale_weight_sqrt,
)
from human_microcircuit.physiology.synaptic_parameters import (
    psp_to_psc,
)

from human_microcircuit.physiology.reference_matrices import (
    indegree_matrix,
    full_mean_rates,
    external_indegrees,
    external_psc_weights,
    mean_psc_matrix,
    tau_syn_ex,
)

from human_microcircuit.physiology.pd14 import (
    external_dc_compensation,
    recurrent_dc_from_network,
)


class ParameterBuilder:
    """
    Build a derived NetworkConfig.
    """

    def __init__(
        self,
        network_config: NetworkConfig,
    ) -> None:
        self._network_config = network_config

    def build(self) -> NetworkConfig:
        """
        Build a derived NetworkConfig.

        The returned object is independent from the original one.
        """

        network = self._network_config.model_copy(deep=True)

        network = self._apply_n_scaling(network)

        network = self._apply_k_scaling(network)

        network = self._apply_psp_to_psc(network)

        network = self._apply_weight_scaling(network)

        network = self._apply_dc_compensation(network)

        network = self._apply_external_poisson_rates(network)

        return network

    def _apply_n_scaling(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        """
        Apply neuron-number scaling.
        """

        scaling = network.scaling

        populations = {}

        for name, population in network.populations.items():

            populations[name] = population.model_copy(
                update={
                    "size": scale_neuron_number(
                        population.size,
                        scaling.N_scaling,
                    )
                }
            )

        return network.model_copy(
            update={
                "populations": populations,
            }
        )

    def _apply_k_scaling(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        """
        Apply indegree scaling.

        Currently scales:
            - recurrent synapse numbers
            - background indegrees

        Synaptic weights and DC compensation are intentionally
        handled in later transformations.
        """

        scaling = network.scaling

        #
        # populations
        #

        populations = {}

        for name, population in network.populations.items():

            populations[name] = population.model_copy(
                update={
                    "background_indegree": (
                        population.background_indegree * scaling.K_scaling
                    )
                }
            )

        #
        # connections
        #

        connections = []

        for connection in network.connections:

            connections.append(
                connection.model_copy(
                    update={
                        "n_synapses": scale_synapse_number(
                            connection.n_synapses,
                            scaling.K_scaling,
                        )
                    }
                )
            )

        return network.model_copy(
            update={
                "populations": populations,
                "connections": connections,
            }
        )

    def _apply_external_poisson_rates(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        """
        Convert biological background rates into effective
        Poisson generator rates.

        PD14:

            effective_rate = bg_rate * K_ext
        """

        inputs = {}

        for pop_name, input_cfg in network.inputs.items():

            K_ext = network.populations[pop_name].background_indegree

            inputs[pop_name] = input_cfg.model_copy(
                update={
                    "rate": input_cfg.rate * K_ext,
                }
            )

        return network.model_copy(
            update={
                "inputs": inputs,
            }
        )

    def _psp_to_psc(
        self,
        psp: float,
        target_population,
    ) -> float:
        """
        Convert a PSP amplitude to a PSC amplitude for a target population.
        """

        params = target_population.neuron.parameters

        return psp_to_psc(
            psp=psp,
            C_m=params.C_m,
            tau_m=params.tau_m,
            tau_syn=params.tau_syn_ex,
        )

    def _convert_connection_weight_to_psc(
        self,
        connection,
        network: NetworkConfig,
    ):
        """
        Convert the connection weight from biological PSP amplitude to
        PSC amplitude.
        """
        target = network.populations[connection.target]

        weight = connection.weight.model_copy(
            update={
                "mean": self._psp_to_psc(
                    connection.weight.mean,
                    target,
                )
            }
        )

        return connection.model_copy(
            update={
                "weight": weight,
            }
        )

    def _convert_input_weight_to_psc(
        self,
        pop_name: str,
        input_cfg,
        network: NetworkConfig,
    ):
        """
        Convert the external input weight from biological PSP amplitude to
        PSC amplitude.
        """
        target = network.populations[pop_name]

        weight = input_cfg.weight.model_copy(
            update={
                "mean": self._psp_to_psc(
                    input_cfg.weight.mean,
                    target,
                )
            }
        )

        return input_cfg.model_copy(
            update={
                "weight": weight,
            }
        )

    def _apply_psp_to_psc(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        """
        Convert biological PSP amplitudes into PSC amplitudes.
        """

        #
        # recurrent connections
        #
        connections = []

        for connection in network.connections:
            connections.append(
                self._convert_connection_weight_to_psc(
                    connection,
                    network,
                )
            )

        #
        # external inputs
        #
        inputs = {}
        for pop_name, input_cfg in network.inputs.items():
            inputs[pop_name] = self._convert_input_weight_to_psc(
                pop_name,
                input_cfg,
                network,
            )

        return network.model_copy(
            update={
                "connections": connections,
                "inputs": inputs,
            }
        )

    def _scale_weight(
        self,
        weight: float,
        K_scaling: float,
    ) -> float:
        """
        Apply square-root synaptic weight scaling.
        """

        return scale_weight_sqrt(
            weight,
            K_scaling,
        )

    def _scale_connection_weight(
        self,
        connection,
        K_scaling: float,
    ):
        """
        Scale synaptic weight for a recurrent connection.
        """
        weight = connection.weight.model_copy(
            update={
                "mean": self._scale_weight(
                    connection.weight.mean,
                    K_scaling,
                )
            }
        )

        return connection.model_copy(
            update={
                "weight": weight,
            }
        )

    def _scale_input_weight(
        self,
        input_cfg,
        K_scaling: float,
    ):
        """
        Scale synaptic weight for an external input.
        """
        weight = input_cfg.weight.model_copy(
            update={
                "mean": self._scale_weight(
                    input_cfg.weight.mean,
                    K_scaling,
                )
            }
        )

        return input_cfg.model_copy(
            update={
                "weight": weight,
            }
        )

    def _apply_weight_scaling(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        """
        Apply square root synaptic weight scaling.

        w -> w / sqrt(K_scaling)
        """

        scaling = network.scaling

        #
        # recurrent
        #
        connections = []
        for connection in network.connections:
            connections.append(
                self._scale_connection_weight(
                    connection,
                    scaling.K_scaling,
                )
            )

        #
        # external
        #
        inputs = {}
        for pop_name, input_cfg in network.inputs.items():
            inputs[pop_name] = self._scale_input_weight(
                input_cfg,
                scaling.K_scaling,
            )
        return network.model_copy(
            update={
                "connections": connections,
                "inputs": inputs,
            }
        )

    def _apply_dc_compensation(
        self,
        network: NetworkConfig,
    ) -> NetworkConfig:
        """
        Apply the Potjans & Diesmann (2014) DC compensation
        required for indegree scaling.
        """

        #
        # Use the biological (unscaled) network as reference.
        #
        original = self._network_config

        if original.reference is None:
            return network

        scaling = original.scaling

        #
        # Reference quantities
        #
        indegrees = indegree_matrix(original)
        mean_rates = full_mean_rates(original)
        K_ext = external_indegrees(original)
        PSC_ext = external_psc_weights(original)

        #
        # Build recurrent PSC matrix (already biological PSC,
        # because PSP->PSC conversion has not been applied to
        # the original network).
        #
        PSC_matrix = mean_psc_matrix(original)
        pop_names = list(original.populations.keys())

        #
        # Recurrent contribution
        #
        tau_syn = tau_syn_ex(original)

        dc_rec = recurrent_dc_from_network(
            mean_PSC_matrix=PSC_matrix,
            indegree_matrix=indegrees,
            mean_rates=mean_rates,
            tau_syn=tau_syn,
            K_scaling=scaling.K_scaling,
        )

        #
        # External contribution
        #
        bg_rates = np.asarray(
            [original.inputs[name].rate for name in pop_names],
            dtype=float,
        )
        dc_ext = external_dc_compensation(
            PSC_ext=PSC_ext,
            K_ext=K_ext,
            bg_rate=bg_rates,
            tau_syn=tau_syn,
            K_scaling=scaling.K_scaling,
        )

        #
        # Update derived network
        #
        populations = {}

        for i, name in enumerate(pop_names):

            population = network.populations[name]

            params = population.neuron.parameters.model_copy(
                update={
                    "I_e": (population.neuron.parameters.I_e + dc_rec[i] + dc_ext[i])
                }
            )

            neuron = population.neuron.model_copy(
                update={
                    "parameters": params,
                }
            )

            populations[name] = population.model_copy(
                update={
                    "neuron": neuron,
                }
            )

        return network.model_copy(
            update={
                "populations": populations,
            }
        )
