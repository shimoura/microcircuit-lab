"""NEST's aeif_cond_exp: adaptive exponential integrate-and-fire neuron with
exponential conductances (Brette & Gerstner, 2005)."""

from microcircuit_lab.backends.brian2.models import NeuronModel

aeif_cond_exp = NeuronModel(
    name="aeif_cond_exp",
    equations="""
    dV_m/dt = (-g_L*(V_m - E_L) + g_L*Delta_T*exp((V_m - V_th)/Delta_T) - g_ex*(V_m - E_ex) - g_in*(V_m - E_in) - w + I_e + I_stim)/C_m : volt (unless refractory)
    dw/dt = (a*(V_m - E_L) - w)/tau_w : amp
    dg_ex/dt = -g_ex/tau_syn_ex : siemens
    dg_in/dt = -g_in/tau_syn_in : siemens
    C_m : farad
    g_L : siemens
    E_L : volt
    V_th : volt
    V_peak : volt
    V_reset : volt
    Delta_T : volt
    t_ref : second
    a : siemens
    b : amp
    tau_w : second
    E_ex : volt
    E_in : volt
    tau_syn_ex : second
    tau_syn_in : second
    I_e : amp
    """,
    threshold="V_m >= V_peak",
    reset="V_m = V_reset; w += b",
    method="euler",
    excitatory="g_ex",
    inhibitory="g_in",
    defaults={
        "C_m": 281.0,
        "g_L": 30.0,
        "E_L": -70.6,
        "V_th": -50.4,
        "V_peak": 0.0,
        "V_reset": -60.0,
        "Delta_T": 2.0,
        "t_ref": 0.0,
        "a": 4.0,
        "b": 80.5,
        "tau_w": 144.0,
        "E_ex": 0.0,
        "E_in": -85.0,
        "tau_syn_ex": 0.2,
        "tau_syn_in": 2.0,
        "I_e": 0.0,
        "V_m": -70.6,
    },
)
