"""Parameters of the two-area toy network.

Synthetic numbers chosen to exercise the template, not a model of cortex: two
areas with different layers and cell types, neuron entries shared by some
populations and split by layer for others, and connections between the areas.

* Area A has L23, L4, L5 and L6, each with E, PV and SOM cells.
* Area B has no L4 (agranular) and adds VIP cells, which exist only here.
* A's PV cells use one neuron entry in L23/L4 and another in L5/L6; B's PV cells
  share one entry in every layer. B's E cells are split the same way as A's PV.

Populations are named ``<area>__<layer>_<cell type>``, e.g. ``B__L23_VIP``.
"""

# One row per population: (area, layer, cell type, number of neurons, neuron entry).
populations = [
    ("A", "L23", "E", 200, "A_E"),
    ("A", "L23", "PV", 25, "A_PV_upper"),
    ("A", "L23", "SOM", 15, "A_SOM"),
    ("A", "L4", "E", 200, "A_E"),
    ("A", "L4", "PV", 25, "A_PV_upper"),
    ("A", "L4", "SOM", 15, "A_SOM"),
    ("A", "L5", "E", 200, "A_E"),
    ("A", "L5", "PV", 25, "A_PV_deep"),
    ("A", "L5", "SOM", 15, "A_SOM"),
    ("A", "L6", "E", 200, "A_E"),
    ("A", "L6", "PV", 25, "A_PV_deep"),
    ("A", "L6", "SOM", 15, "A_SOM"),
    ("B", "L23", "E", 200, "B_E_upper"),
    ("B", "L23", "PV", 25, "B_PV"),
    ("B", "L23", "SOM", 15, "B_SOM"),
    ("B", "L23", "VIP", 10, "B_VIP"),
    ("B", "L5", "E", 200, "B_E_deep"),
    ("B", "L5", "PV", 25, "B_PV"),
    ("B", "L5", "SOM", 15, "B_SOM"),
    ("B", "L5", "VIP", 10, "B_VIP"),
    ("B", "L6", "E", 200, "B_E_deep"),
    ("B", "L6", "PV", 25, "B_PV"),
    ("B", "L6", "SOM", 15, "B_SOM"),
    ("B", "L6", "VIP", 10, "B_VIP"),
]

excitatory_types = {"E"}

# Neuron entries: iaf_psc_exp, each entry changing a few of the BASE parameters
# (pF, ms, mV). Different synaptic time constants per entry also test the DC
# compensation of a scaled network.
neuron_model = "iaf_psc_exp"
base_neuron = {
    "C_m": 250.0,
    "tau_m": 10.0,
    "tau_syn_ex": 0.5,
    "tau_syn_in": 0.5,
    "E_L": -65.0,
    "V_reset": -65.0,
    "V_th": -50.0,
    "t_ref": 2.0,
    "I_e": 0.0,
}
neurons = {
    "A_E": {},
    "A_PV_upper": {"C_m": 100.0, "tau_m": 5.0, "t_ref": 1.0},
    "A_PV_deep": {"C_m": 150.0, "tau_m": 5.0, "t_ref": 1.0},
    "A_SOM": {"C_m": 200.0, "tau_m": 15.0, "tau_syn_in": 1.0},
    "B_E_upper": {"tau_syn_ex": 2.0, "tau_syn_in": 4.0},
    "B_E_deep": {"C_m": 300.0, "tau_m": 12.0},
    "B_PV": {"C_m": 100.0, "tau_m": 5.0, "t_ref": 1.0},
    "B_SOM": {"C_m": 200.0, "tau_m": 15.0},
    "B_VIP": {"C_m": 150.0, "tau_m": 12.0},
}

# Initial membrane potentials (mV), the same for all populations.
v0_mean = -58.0
v0_std = 10.0

# Connection probability within an area, p_local[source type][target type],
# times layer_factor (1 within a layer, 0.2 between layers). PV cells inhibit
# E and PV, SOM cells inhibit all but SOM, VIP cells inhibit mostly SOM.
p_local = {
    "E": {"E": 0.10, "PV": 0.30, "SOM": 0.20, "VIP": 0.10},
    "PV": {"E": 0.40, "PV": 0.40, "SOM": 0.10, "VIP": 0.05},
    "SOM": {"E": 0.30, "PV": 0.20, "SOM": 0.00, "VIP": 0.10},
    "VIP": {"E": 0.05, "PV": 0.05, "SOM": 0.20, "VIP": 0.00},
}
layer_factor = {"same": 1.0, "other": 0.2}

# Between areas: only E cells project, onto E and PV cells of every layer of
# the other area. The delay is the distance over the conduction speed.
p_inter_area = {"E": 0.02, "PV": 0.02}
distance_mm = 20.0
conduction_speed_mm_per_ms = 3.5

# Synapses: psp amplitudes in mV per source type, delays in ms.
psp = {"E": 0.5, "PV": -1.0, "SOM": -1.0, "VIP": -1.0}
weight_rel_std = 0.1
delay_exc = 1.5
delay_inh = 0.75
delay_rel_std = 0.5
# Drawn weights keep their sign and drawn delays stay at delay_min (ms) or more,
# both drawn again past the bound. delay_min is half the 0.1 ms time step: a
# shorter delay would round to 0 steps.
bound_mode = "redraw"
delay_min = 0.05

# Background Poisson input: rate per synapse (spikes/s), psp (mV), delay (ms)
# and indegree per target cell type.
bg_rate = 8.0
bg_psp = 0.15
bg_delay = 1.5
k_ext = {"E": 850, "PV": 1390, "SOM": 520, "VIP": 710}

# Mean rates of the full-scale network (spikes/s): the mean of four 2 s runs of
# this network (seeds 1, 2, 3, 42; the first 200 ms left out). Needed for the DC
# compensation when the network is scaled.
full_mean_rates = {
    "A__L23_E": 3.483,
    "A__L23_PV": 5.594,
    "A__L23_SOM": 4.296,
    "A__L4_E": 3.586,
    "A__L4_PV": 5.589,
    "A__L4_SOM": 4.148,
    "A__L5_E": 3.462,
    "A__L5_PV": 5.339,
    "A__L5_SOM": 3.954,
    "A__L6_E": 3.465,
    "A__L6_PV": 5.611,
    "A__L6_SOM": 3.88,
    "B__L23_E": 8.819,
    "B__L23_PV": 14.161,
    "B__L23_SOM": 14.944,
    "B__L23_VIP": 7.556,
    "B__L5_E": 8.262,
    "B__L5_PV": 13.506,
    "B__L5_SOM": 13.852,
    "B__L5_VIP": 7.167,
    "B__L6_E": 8.25,
    "B__L6_PV": 13.339,
    "B__L6_SOM": 14.5,
    "B__L6_VIP": 6.528,
}

# --- Only for toy_two_areas_advanced (advanced.py) ---------------------------

# Each neuron's threshold is drawn around its entry's V_th, with this spread (mV).
v_th_std = 1.0

# The connections between areas use a depressing synapse (tsodyks2_synapse).
depressing_synapse = {"U": 0.5, "tau_rec": 200.0, "tau_fac": 0.0}

# B__L23_E gets a neuron with one receptor port per kind of input, each with its
# own synaptic time constant (ms). Ports 1 and 2 have the time constants of its
# entry B_E_upper (tau_syn_ex 2, tau_syn_in 4); port 3 is slow, for the input
# from the other area. Written in port order: the neuron's tau_syn list is the
# values of receptor_port_tau_syn in this order.
receptor_port_population = "B__L23_E"
receptor_port_neuron = "B_E_upper"
receptor_port_model = "iaf_psc_exp_multisynapse"
receptor_ports = {"excitatory": 1, "inhibitory": 2, "other_area": 3}
receptor_port_tau_syn = {"excitatory": 2.0, "inhibitory": 4.0, "other_area": 20.0}

# --- Only for toy_two_areas_clustered (clustered.py) -------------------------

# Each population is split into this many clusters.
clusters = 3

# The clustering rule (see clustered.py): the
# weights of E -> E connections are multiplied by j_e_plus within a cluster;
# those of every connection with an inhibitory source or target by
# J_I_plus = 1 + r_j * (j_e_plus - 1). Between clusters, J_minus =
# (clusters - J_plus) / (clusters - 1), which keeps each neuron's mean input.
# j_e_plus must stay below clusters.
j_e_plus = 2.0
r_j = 0.75

# The same, for the connections between areas (cluster i of one area to
# cluster i of the other).
between_areas_j_e_plus = 2.0
between_areas_r_j = 0.75
