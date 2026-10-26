"""NEST's iaf_psc_exp_multisynapse: iaf_psc_exp with one exponential current
per receptor port, as many as ``tau_syn`` has values."""

from microcircuit_lab.backends.brian2.models import NeuronModel


def equations(parameters: dict) -> str:
    if "tau_syn" not in parameters:
        raise ValueError("iaf_psc_exp_multisynapse needs tau_syn, one value per receptor port.")
    ports = range(1, len(parameters["tau_syn"]) + 1)
    currents = " + ".join(f"I_syn_{port}" for port in ports)
    synapses = "\n".join(
        f"dI_syn_{port}/dt = -I_syn_{port}/tau_syn_{port} : amp\ntau_syn_{port} : second" for port in ports
    )
    return f"""
    dV_m/dt = -(V_m - E_L)/tau_m + ({currents} + I_e + I_stim)/C_m : volt (unless refractory)
    {synapses}
    E_L : volt
    C_m : farad
    tau_m : second
    t_ref : second
    V_th : volt
    V_reset : volt
    I_e : amp
    """


iaf_psc_exp_multisynapse = NeuronModel(
    name="iaf_psc_exp_multisynapse",
    equations=equations,
    threshold="V_m >= V_th",
    reset="V_m = V_reset",
    receptor_port="I_syn_{port}",
    defaults={
        "E_L": -70.0,
        "C_m": 250.0,
        "tau_m": 10.0,
        "t_ref": 2.0,
        "V_th": -55.0,
        "V_reset": -70.0,
        "I_e": 0.0,
        "V_m": -70.0,
    },
)
