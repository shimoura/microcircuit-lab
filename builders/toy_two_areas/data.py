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
POPULATIONS = [
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

EXCITATORY_TYPES = {"E"}

# Neuron entries: iaf_psc_exp, each entry changing a few of the BASE parameters
# (pF, ms, mV). Different synaptic time constants per entry also test the DC
# compensation of a scaled network.
NEURON_MODEL = "iaf_psc_exp"
BASE_NEURON = {
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
NEURONS = {
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
V0_MEAN = -58.0
V0_STD = 10.0

# Connection probability within an area, P_LOCAL[source type][target type],
# times LAYER_FACTOR (1 within a layer, 0.2 between layers). PV cells inhibit
# E and PV, SOM cells inhibit all but SOM, VIP cells inhibit mostly SOM.
P_LOCAL = {
    "E": {"E": 0.10, "PV": 0.30, "SOM": 0.20, "VIP": 0.10},
    "PV": {"E": 0.40, "PV": 0.40, "SOM": 0.10, "VIP": 0.05},
    "SOM": {"E": 0.30, "PV": 0.20, "SOM": 0.00, "VIP": 0.10},
    "VIP": {"E": 0.05, "PV": 0.05, "SOM": 0.20, "VIP": 0.00},
}
LAYER_FACTOR = {"same": 1.0, "other": 0.2}

# Between areas: only E cells project, onto E and PV cells of every layer of
# the other area. The delay is the distance over the conduction speed.
P_INTER_AREA = {"E": 0.02, "PV": 0.02}
DISTANCE_MM = 20.0
CONDUCTION_SPEED_MM_PER_MS = 3.5

# Synapses: PSP amplitudes in mV per source type, delays in ms.
PSP = {"E": 0.5, "PV": -1.0, "SOM": -1.0, "VIP": -1.0}
WEIGHT_REL_STD = 0.1
DELAY_EXC = 1.5
DELAY_INH = 0.75
DELAY_REL_STD = 0.5

# Background Poisson input: rate per synapse (spikes/s), PSP (mV), delay (ms)
# and indegree per target cell type.
BG_RATE = 8.0
BG_PSP = 0.15
BG_DELAY = 1.5
K_EXT = {"E": 850, "PV": 1390, "SOM": 520, "VIP": 710}

# Mean rates of the full-scale network (spikes/s): the mean of four 2 s runs of
# this network (seeds 1, 2, 3, 42; the first 200 ms left out). Needed for the DC
# compensation when the network is scaled.
FULL_MEAN_RATES = {
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
V_TH_STD = 1.0

# The connections between areas use a depressing synapse (tsodyks2_synapse).
DEPRESSING_SYNAPSE = {"U": 0.5, "tau_rec": 200.0, "tau_fac": 0.0}

# B__L23_E gets a neuron with one receptor port per kind of input, each with its
# own synaptic time constant (ms). Ports 1 and 2 have the time constants of its
# entry B_E_upper (tau_syn_ex 2, tau_syn_in 4); port 3 is slow, for the input
# from the other area. Written in port order: the neuron's tau_syn list is the
# values of RECEPTOR_PORT_TAU_SYN in this order.
RECEPTOR_PORT_POPULATION = "B__L23_E"
RECEPTOR_PORT_NEURON = "B_E_upper"
RECEPTOR_PORT_MODEL = "iaf_psc_exp_multisynapse"
RECEPTOR_PORTS = {"excitatory": 1, "inhibitory": 2, "other_area": 3}
RECEPTOR_PORT_TAU_SYN = {"excitatory": 2.0, "inhibitory": 4.0, "other_area": 20.0}

# --- Only for toy_two_areas_clustered (clustered.py) -------------------------

# Each population is split into this many clusters.
CLUSTERS = 3

# The clustering rule (see clustered.py): the
# weights of E -> E connections are multiplied by J_E_PLUS within a cluster;
# those of every connection with an inhibitory source or target by
# J_I_plus = 1 + R_J * (J_E_PLUS - 1). Between clusters, J_minus =
# (CLUSTERS - J_plus) / (CLUSTERS - 1), which keeps each neuron's mean input.
# J_E_PLUS must stay below CLUSTERS.
J_E_PLUS = 2.0
R_J = 0.75

# The same, for the connections between areas (cluster i of one area to
# cluster i of the other).
BETWEEN_AREAS_J_E_PLUS = 2.0
BETWEEN_AREAS_R_J = 0.75
