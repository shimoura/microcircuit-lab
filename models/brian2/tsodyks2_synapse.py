"""NEST's tsodyks2_synapse: short-term depression and facilitation
(Tsodyks & Markram, 1997), updated at each spike as NEST does."""

from microcircuit_lab.backends.brian2.models import SynapseModel

# tau_fac 0 means no facilitation: u is then U at each spike. The int(...)
# factors keep that from dividing by zero.
tsodyks2_synapse = SynapseModel(
    name="tsodyks2_synapse",
    model="""
    U : 1 (constant)
    tau_rec : second (constant)
    tau_fac : second (constant)
    u : 1
    x : 1
    t_last : second
    """,
    on_pre="""
    x = 1 + (x - x*u - 1)*exp(-(t - t_last)/tau_rec)
    u = U + u*(1 - U)*int(tau_fac > 0*ms)*exp(-(t - t_last)/(tau_fac + int(tau_fac <= 0*ms)*ms))
    {target} += w_syn*u*x
    t_last = t
    """,
    defaults={"U": 0.5, "tau_rec": 800.0, "tau_fac": 0.0, "u": 0.5, "x": 1.0},
)
