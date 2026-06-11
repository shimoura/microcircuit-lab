from math import log

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

full_num_neurons = np.array([20683, 5834, 21915, 5479, 4850, 1065, 14395, 2948])

conn_probs = np.array(
    [
        [0.1009, 0.1689, 0.0437, 0.0818, 0.0323, 0.0, 0.0076, 0.0],
        [0.1346, 0.1371, 0.0316, 0.0515, 0.0755, 0.0, 0.0042, 0.0],
        [0.0077, 0.0059, 0.0497, 0.1350, 0.0067, 0.0003, 0.0453, 0.0],
        [0.0691, 0.0029, 0.0794, 0.1597, 0.0033, 0.0, 0.1057, 0.0],
        [0.1004, 0.0622, 0.0505, 0.0057, 0.0831, 0.3726, 0.0204, 0.0],
        [0.0548, 0.0269, 0.0257, 0.0022, 0.0600, 0.3158, 0.0086, 0.0],
        [0.0156, 0.0066, 0.0211, 0.0166, 0.0572, 0.0197, 0.0396, 0.2252],
        [0.0364, 0.0010, 0.0034, 0.0005, 0.0277, 0.0080, 0.0658, 0.1443],
    ]
)


def num_synapses_from_conn_prob(conn_prob, n_source, n_target):
    if conn_prob <= 0.0:
        return 0

    prod = n_source * n_target

    return round(log(1.0 - conn_prob) / log((prod - 1.0) / prod))


for target_index, target in enumerate(populations):

    for source_index, source in enumerate(populations):

        n_syn = num_synapses_from_conn_prob(
            conn_probs[target_index, source_index],
            full_num_neurons[source_index],
            full_num_neurons[target_index],
        )

        print(f"{target:5s} <- {source:5s} : {n_syn}")
