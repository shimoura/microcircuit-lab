"""Potjans & Diesmann (2014) microcircuit parameters.

Sources:

* Potjans TC, Diesmann M (2014). The cell-type specific cortical microcircuit:
  relating structure and activity in a full-scale spiking network model.
  Cerebral Cortex 24(3):785-806. https://doi.org/10.1093/cercor/bhs358
* The official PyNEST implementation, INM-6/microcircuit-PD14-model, commit
  f79f8acc22f44c879185a4fe3443d20b153a4d4e, file
  ``PyNEST/src/microcircuit/network_params.py`` (``net_dict``). Names below
  follow that file; values are copied from it.

The neuron numbers, connection probabilities, synaptic weights and delays,
neuron parameters and background input are given in the publication. The
optimized initial membrane potentials (``V0_mean``, ``V0_std``) and the
reference rates (``full_mean_rates``) come from the official implementation
only.

Populations are ordered L23_E, L23_I, L4_E, L4_I, L5_E, L5_I, L6_E, L6_I (the
official names without the underscore before E/I). Matrices are indexed
[target, source].
"""

import numpy as np

populations = [
    "L23_E",
    "L23_I",
    "L4_E",
    "L4_I",
    "L5_E",
    "L5_I",
    "L6_E",
    "L6_I",
]

full_num_neurons = np.array(
    [
        20683,
        5834,
        21915,
        5479,
        4850,
        1065,
        14395,
        2948,
    ]
)

connection_probabilities = np.array(
    [
        [0.1009, 0.1689, 0.0437, 0.0818, 0.0323, 0.0000, 0.0076, 0.0000],
        [0.1346, 0.1371, 0.0316, 0.0515, 0.0755, 0.0000, 0.0042, 0.0000],
        [0.0077, 0.0059, 0.0497, 0.1350, 0.0067, 0.0003, 0.0453, 0.0000],
        [0.0691, 0.0029, 0.0794, 0.1597, 0.0033, 0.0000, 0.1057, 0.0000],
        [0.1004, 0.0622, 0.0505, 0.0057, 0.0831, 0.3726, 0.0204, 0.0000],
        [0.0548, 0.0269, 0.0257, 0.0022, 0.0600, 0.3158, 0.0086, 0.0000],
        [0.0156, 0.0066, 0.0211, 0.0166, 0.0572, 0.0197, 0.0396, 0.2252],
        [0.0364, 0.0010, 0.0034, 0.0005, 0.0277, 0.0080, 0.0658, 0.1443],
    ]
)

# Synapses: mean PSPs in mV (inhibitory ones are g times the excitatory one; the
# L4_E -> L23_E PSP is twice PSP_exc_mean) and mean delays in ms.
PSP_exc_mean = 0.15
g = -4.0
weight_rel_std = 0.1
delay_exc_mean = 1.5
delay_inh_mean = 0.75
delay_rel_std = 0.5

# Background (cortico-cortical) input: Poisson rate per synapse in spikes/s,
# indegree per population, delay in ms.
bg_rate = 8.0
K_ext = np.array([1600, 1500, 2100, 1900, 2000, 1900, 2900, 2100])
delay_poisson = 1.5

# Neuron model and parameters, the same for all populations (pF, ms, mV);
# tau_syn is used for excitatory and inhibitory synapses.
neuron_model = "iaf_psc_exp"
neuron_params = {
    "C_m": 250.0,
    "tau_m": 10.0,
    "tau_syn": 0.5,
    "E_L": -65.0,
    "V_reset": -65.0,
    "V_th": -50.0,
    "t_ref": 2.0,
}

# Initial membrane potentials in mV, "optimized" per population.
V0_mean = [-68.28, -63.16, -63.33, -63.45, -63.11, -61.66, -66.72, -61.43]
V0_std = [5.36, 4.57, 4.74, 4.94, 4.94, 4.55, 5.46, 4.48]

# Mean rates of the full-scale network in spikes/s, from one simulation of the
# official implementation; used for the scaling compensation and as a
# reference. One run only, so not a verification target on its own.
full_mean_rates = np.array([0.903, 2.965, 4.414, 5.876, 7.569, 8.633, 1.105, 7.829])
