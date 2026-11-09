"""Jiang et al. (2024) microcircuit parameters, with static synapses (the "Base" model).

Sources:

* Jiang H-J, Qi G, Duarte R, Feldmeyer D, van Albada SJ (2024). A layered
  microcircuit model of somatosensory cortex with three interneuron types and
  cell-type-specific short-term plasticity. Cerebral Cortex 34(9):bhae378.
  https://doi.org/10.1093/cercor/bhae378
* The official code, https://zenodo.org/doi/10.5281/zenodo.10069507. 

Populations are ordered as in the publication, with E for its Exc. Matrices are
indexed [target, source].
"""

# One row per population: (name, number of neurons, neuron entry). Table 1; all
# VIP cells are one population, in L2/3.
populations = [
    ("L23_E", 1691, "E_upper"),
    ("L23_PV", 90, "PV_upper"),
    ("L23_SOM", 74, "SOM_upper"),
    ("L23_VIP", 85, "VIP"),
    ("L4_E", 1656, "E_upper"),
    ("L4_PV", 85, "PV_upper"),
    ("L4_SOM", 48, "SOM_upper"),
    ("L5_E", 1095, "E_deep"),
    ("L5_PV", 109, "PV_deep"),
    ("L5_SOM", 105, "SOM_deep"),
    ("L6_E", 1288, "E_deep"),
    ("L6_PV", 56, "PV_deep"),
    ("L6_SOM", 66, "SOM_deep"),
]

# Neuron entries (Table 2; code: ctsp in model/net_dict.json), in pF, ms and mV:
# upper for L2/3 and L4, deep for L5 and L6. V_reset is E_L. tau_m is the in vitro
# value lowered towards the awake state, by 50.9 % for E cells and 4.9 % for the others.
neuron_model = "iaf_psc_exp"
neurons = {
    "E_upper": {"tau_m": 5.1555, "C_m": 229.75929978118162, "E_L": -67.4, "V_th": -41.5},
    "PV_upper": {"tau_m": 2.9481, "C_m": 93.93939393939394, "E_L": -66.4, "V_th": -41.6},
    "SOM_upper": {"tau_m": 11.2218, "C_m": 123.3019853709509, "E_L": -59.9, "V_th": -41.8},
    "VIP": {"tau_m": 10.3659, "C_m": 86.5079365079365, "E_L": -65.7, "V_th": -43.7},
    "E_deep": {"tau_m": 5.944234042553192, "C_m": 269.2405328308603, "E_L": -63.212765957446805, "V_th": -45.163829787234036},
    "PV_deep": {"tau_m": 3.804, "C_m": 80.97165991902834, "E_L": -67.1, "V_th": -42.3},
    "SOM_deep": {"tau_m": 11.1267, "C_m": 146.80050188205772, "E_L": -63.2, "V_th": -48.1},
}

# The same for all neurons (ms; Table 4 and Methods).
tau_syn_ex = 2.0
tau_syn_in = 4.0
t_ref = 2.0

# Initial membrane potentials in mV, from the code only (neuron_params in
# model/net_dict.json).
V0_mean = -62.0
V0_std = 5.0

# Connection probabilities (Fig. 3; code: conn/conn.csv with the missing entries
# filled in by Helper.hybrid_conn, which replaces conn_probs in model/net_dict.json).
connection_probabilities = [
    [0.0673, 0.2705, 0.2795, 0.0426, 0.1100, 0.0203, 0.0455, 0.0239, 0.0015, 0.0147, 0.0000, 0.0000, 0.0000],
    [0.2849, 0.3182, 0.1181, 0.0549, 0.0040, 0.0165, 0.0316, 0.0005, 0.0013, 0.0140, 0.0001, 0.0001, 0.0056],
    [0.2428, 0.2909, 0.0000, 0.2713, 0.0036, 0.0118, 0.0442, 0.0003, 0.0015, 0.0208, 0.0000, 0.0000, 0.0000],
    [0.1600, 0.2059, 0.4633, 0.0626, 0.0023, 0.0103, 0.0171, 0.0002, 0.0010, 0.0059, 0.0000, 0.0001, 0.0051],
    [0.0133, 0.0353, 0.0595, 0.0702, 0.0994, 0.3739, 0.1975, 0.0061, 0.0279, 0.0520, 0.0000, 0.0021, 0.0241],
    [0.0359, 0.0161, 0.0229, 0.0532, 0.3739, 0.2878, 0.3630, 0.0085, 0.0278, 0.0473, 0.0012, 0.0027, 0.0182],
    [0.0361, 0.0182, 0.0241, 0.0486, 0.1902, 0.3320, 0.0116, 0.0095, 0.0321, 0.0468, 0.0017, 0.0021, 0.0226],
    [0.0860, 0.0420, 0.0941, 0.0616, 0.0874, 0.0698, 0.0756, 0.0982, 0.3956, 0.1514, 0.0098, 0.0177, 0.0506],
    [0.0169, 0.0047, 0.0107, 0.0195, 0.0345, 0.0305, 0.0229, 0.3956, 0.2462, 0.2406, 0.0045, 0.0129, 0.0257],
    [0.0158, 0.0042, 0.0103, 0.0192, 0.0375, 0.0302, 0.0254, 0.2049, 0.3114, 0.0058, 0.0058, 0.0148, 0.0317],
    [0.0000, 0.0018, 0.0032, 0.0078, 0.0298, 0.0151, 0.0097, 0.0396, 0.0195, 0.0166, 0.0215, 0.3956, 0.1514],
    [0.0027, 0.0001, 0.0002, 0.0021, 0.0050, 0.0023, 0.0005, 0.0163, 0.0000, 0.0034, 0.3956, 0.2462, 0.2406],
    [0.0022, 0.0000, 0.0002, 0.0011, 0.0046, 0.0020, 0.0004, 0.0153, 0.0000, 0.0022, 0.2049, 0.3114, 0.0058],
]

# Simulation settings: the publication's resting state runs for 15 s at a 0.1 ms
# time step (ms; Methods). The seed and threads are this builder's choice.
t_sim = 15000.0
resolution = 0.1
rng_seed = 42
local_num_threads = 16

# The time window of the raster plot in Fig. 6 (ms).
raster_begin = 10000.0
raster_end = 10200.0

# The time window the publication analyses (ms; Methods).
analysis_begin = 10000.0
analysis_end = 15000.0

# Experimental firing rates (spikes/s): first quartile, median and third quartile
# of the non-whisking state in Yu et al. (2019), Table 1 (Table 5; code:
# populations.csv, which also has the median of L4_E that Table 5 leaves out).
experiment_rates = {
    "L23_E": [0.5, 0.6, 4.5],
    "L23_PV": [7.5, 11.7, 23.3],
    "L23_SOM": [0.03, 0.4, 4.1],
    "L23_VIP": [8.5, 11.1, 21.0],
    "L4_E": [0.0, 0.1, 0.7],
    "L4_PV": [4.3, 7.8, 14.7],
    "L4_SOM": [0.3, 0.6, 4.9],
    "L5_E": [2.7, 5.2, 11.2],
    "L5_PV": [4.3, 7.6, 8.7],
    "L5_SOM": [0.2, 0.8, 3.6],
    "L6_E": [0.4, 2.6, 11.5],
    "L6_PV": [4.6, 17.2, 22.0],
    "L6_SOM": [0.5, 1.7, 6.9],
}

# The colors of the publication's figures (code: populations.csv).
cell_type_colors = {"E": "#004488", "PV": "#994455", "SOM": "#997700", "VIP": "#EE99AA"}

# Synapses: lognormal weights given as mean PSPs in mV, with a standard deviation
# equal to the mean (Table 3; inhibitory PSPs are g times the excitatory one), and
# lognormal delays in ms (Table 4).
psp_exc = 0.5
g = -4.0
weight_rel_std = 1.0
delay_exc_mean = 1.36
delay_exc_std = 0.51
delay_inh_mean = 1.43
delay_inh_std = 1.09
# Drawn delays below the time step are drawn again, as in the code.
delay_min = resolution

# Background input: one Poisson train per neuron at a rate per cell type in spikes/s
# (Supplementary Material, "Optimization of the Background Input"; code: Ks_static
# in simulate.py, which replaces K_ext in model/net_dict.json), with a fixed PSP in
# mV and a delay of the time step in ms.
bg_rate = {"E": 5000.0, "PV": 6900.0, "SOM": 2500.0, "VIP": 3300.0}
bg_indegree = 1
bg_psp = 0.5
bg_delay = resolution

# Mean rates of the Base model in spikes/s, over 20 simulations of the official code
# (snakes_main.zip, snake_gs-static/results_pop.csv, fr_data_mu); Table 5 gives them
# rounded to one decimal.
full_mean_rates = {
    "L23_E": 2.109,
    "L23_PV": 15.554,
    "L23_SOM": 2.475,
    "L23_VIP": 10.168,
    "L4_E": 0.516,
    "L4_PV": 10.416,
    "L4_SOM": 2.546,
    "L5_E": 2.007,
    "L5_PV": 20.195,
    "L5_SOM": 0.984,
    "L6_E": 2.988,
    "L6_PV": 38.44,
    "L6_SOM": 5.826,
}
