"""NEST's iaf_psc_exp: leaky integrate-and-fire neuron with exponential
post-synaptic currents."""

from microcircuit_lab.backends.brian2.models import NeuronModel

iaf_psc_exp = NeuronModel(
    name="iaf_psc_exp",
    equations="""
    dV_m/dt = -(V_m - E_L)/tau_m + (I_syn_ex + I_syn_in + I_e + I_stim)/C_m : volt (unless refractory)
    dI_syn_ex/dt = -I_syn_ex/tau_syn_ex : amp
    dI_syn_in/dt = -I_syn_in/tau_syn_in : amp
    E_L : volt
    C_m : farad
    tau_m : second
    tau_syn_ex : second
    tau_syn_in : second
    t_ref : second
    V_th : volt
    V_reset : volt
    I_e : amp
    """,
    threshold="V_m >= V_th",
    reset="V_m = V_reset",
    excitatory="I_syn_ex",
    inhibitory="I_syn_in",
    defaults={
        "E_L": -70.0,
        "C_m": 250.0,
        "tau_m": 10.0,
        "tau_syn_ex": 2.0,
        "tau_syn_in": 2.0,
        "t_ref": 2.0,
        "V_th": -55.0,
        "V_reset": -70.0,
        "I_e": 0.0,
        "V_m": -70.0,
    },
)
