# Brian2

The same network files run on [Brian2](https://brian2.readthedocs.io):

```bash title="Terminal"
pip install "microcircuit_lab[brian2] @ git+https://github.com/shimoura/microcircuit-lab"
microcircuit-lab run --network toy --backend brian2
```

In a clone: `pip install -e ".[brian2]"`. Brian2 2.10 needs Python 3.12 or newer. From Python: `Simulation.from_yaml(network_name="toy", backend="brian2")`.

| | NEST | Brian2 |
| :--- | :--- | :--- |
| Neuron and synapse models | built in | a Python definition in your project's `extensions/brian2/`; the examples bring the ones they use |
| Threads | `local_num_threads` | one by default; `local_num_threads` with `cpp_standalone` ([Speed](#speed)) |
| Several MPI processes | yes, if built from source | no (Brian2 has none) |

The two give the same statistics (rates, CV), not the same spike times: [Tutorial 6](tutorials/6_nest_and_brian2.ipynb) compares them.

## Choosing Brian2 in a simulation file (optional)

A simulation file can name the simulator and its options, so a profile of your own, e.g. `configs/simulation/toy_brian2.yaml`, runs the network on Brian2 (`--simulation toy_brian2`):

```yaml
backend:
  name: brian2                 # default: nest
  options:                     # passed to the backend as they are
    device: cpp_standalone
```

- `--backend`, the `--brian2-...` flags and the `backend`/`backend_options` arguments override it.
- The options belong to the simulator named with them: with `--backend nest`, a Brian2 profile's options are left out.
- The run's `config.yaml` records the simulator and the options used.

## Models of your own

Each model that `neurons.yaml` and `synapses.yaml` name is a `NeuronModel` or a `SynapseModel` in a Python file in `extensions/brian2/` (or in a module given with `--extensions`). `static_synapse` is built in. A name Brian2 can't find stops the run, with a message, before anything is built.

You need one only for a model the examples don't have: each example has the models its networks use (e.g. [the toy's](https://github.com/shimoura/microcircuit-lab/tree/main/examples/toy/extensions/brian2)), and `init` copies them with the example.

```python
# extensions/brian2/my_lif.py
from microcircuit_lab.backends.brian2.models import NeuronModel

my_lif = NeuronModel(
    name="my_lif",
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
    defaults={"E_L": -70.0, "C_m": 250.0, "tau_m": 10.0, "tau_syn_ex": 2.0, "tau_syn_in": 2.0,
              "t_ref": 2.0, "V_th": -55.0, "V_reset": -70.0, "V_m": -70.0, "I_e": 0.0},
)
```

- **Units:** `defaults` and the config files use the package's [units](network-files.md#units) (mV, ms, pF, pA, nS, Hz); the equations use Brian2's.
- **Parameters:** each one is declared in the equations. A parameter in `neurons.yaml` that the model doesn't have, or one with no value, is an error.
- **Currents:** `I_stim` is the current of `dc` stimuli. `I_e` is needed only where `neurons.yaml` sets it or scaling adds its compensation current; declare it with a default of 0.0.
- **Where a weight goes:** to `excitatory` or `inhibitory`, as its sign says. If the synapse has a `receptor_port`, to `receptor_port` instead (e.g. `"I_syn_{port}"`, or a variable by name such as `g_ampa`). A weight onto a conductance adds its size, as in NEST.
- **List parameters:** `tau_syn: [0.5, 2.0]` sets `tau_syn_1` and `tau_syn_2`. When their number varies, `equations` can be a function of the parameters ([`iaf_psc_exp_multisynapse.py`](https://github.com/shimoura/microcircuit-lab/blob/main/examples/toy_two_areas/extensions/brian2/iaf_psc_exp_multisynapse.py)).

### Synapse models (optional)

A `SynapseModel` takes Brian2's own forms. An STDP synapse, for example:

```python
from microcircuit_lab.backends.brian2.models import SynapseModel

stdp = SynapseModel(
    name="stdp",
    model="dapre/dt = -apre/tau_plus : 1 (event-driven)\ndapost/dt = -apost/tau_minus : 1 (event-driven)\n"
    "tau_plus : second (constant)\ntau_minus : second (constant)\nw_max : amp (constant)",
    on_pre="{target} += w_syn\napre += 0.01\nw_syn = clip(w_syn + apost*pA, 0*pA, w_max)",
    on_post="apost -= 0.012\nw_syn = clip(w_syn + apre*pA, 0*pA, w_max)",
    defaults={"tau_plus": 20.0, "tau_minus": 20.0, "w_max": 100.0},
)
```

- `model` holds the synapse's variables; the weight `w_syn` is added.
- `on_pre` and `on_post` are code, or a dict of pathways to code; `{target}` is the variable the connection adds to.
- `delays` gives the delay of each pathway other than `pre` (the connection's delay sets `pre`); `method` is the integration method.
- A gap junction is a summed variable, e.g. `I_gap_post = g_gap*(V_m_pre - V_m_post) : amp (summed)` with `on_pre=""`; the target neuron declares `I_gap`, with a default.
- A model to start from: the two-area toy's short-term plasticity synapse, [`tsodyks2_synapse.py`](https://github.com/shimoura/microcircuit-lab/blob/main/examples/toy_two_areas/extensions/brian2/tsodyks2_synapse.py).

## Connection rules of your own (optional)

A `rule` other than the shared ones is a `ConnectionRule` in `extensions/brian2/`. Its `condition`, `p` and `n` are the arguments of Brian2's `Synapses.connect`: which pairs may connect, the probability that such a pair does, and how many synapses it gets.

```python
# extensions/brian2/rules.py
from microcircuit_lab.backends.brian2.models import ConnectionRule

ring = ConnectionRule(name="ring", condition="abs(index_pre - index_post) <= width", p="p0")
```

```yaml
# connectivity.yaml
- {source: E, target: E, rule: ring, width: 10, p0: 0.5, allow_autapses: false, weight: {...}, delay: {...}}
```

- The expressions can use the connection's arguments (`width`, `p0`), the neurons' variables (`V_m_pre`, `V_m_post`), and `index_pre` / `index_post`, each neuron's index in its population.
- In a CSV connection table, each argument is a column.
- An argument no expression uses stops the run: most likely a misspelled name.
- Scaling a network model with such a rule isn't implemented yet: it stops with an error. Scale it in its builder instead.

## Distributions of your own (optional)

A `distribution` other than the shared ones is a `Distribution` in `extensions/brian2/`: a Brian2 `expression` for each value, in the package's units (pA or nS for a weight, ms for a delay, the variable's unit for a neuron value).

```python
# extensions/brian2/distributions.py
from microcircuit_lab.backends.brian2.models import Distribution

exponential = Distribution(name="exponential", expression="-beta*log(1 - rand())")
decay = Distribution(name="decay", expression="mean * exp(-abs(index_pre - index_post) / length)", redraw_rounds=0)
```

```yaml
# connectivity.yaml
- {source: E, target: E, rule: fixed_indegree, indegree: 100,
   weight: {distribution: decay, mean: 87.8, length: 20, lower_bound: 0, bound_mode: redraw, unit: pA},
   delay: {...}}
```

- The expression can use the entry's fields (`mean`, `std`, `min`, `max`), its arguments (`length`), and, for a weight or a delay, the neurons' variables and `index_pre` / `index_post`.
- A weight needs `mean`: its sign says whether the weight is excitatory or inhibitory. The expression must give values of that sign; the core can't check it.
- An argument the expression doesn't use stops the run.
- `bound_mode: redraw` needs `redraw_rounds`: the value is drawn again that many times, then set to the bound (0 sets it at once). Without it, an entry with `redraw` stops the run before building. `clip` needs nothing.
- Scaling the synapses (`K_scaling` other than 1) with weights from such a distribution isn't implemented yet: it stops with an error (scale them in the builder). Delays are fine; scaling leaves them alone.
- Background inputs and stimuli take the shared distributions; other distributions aren't implemented yet for them.
- The toy's [`distributions.py`](https://github.com/shimoura/microcircuit-lab/blob/main/examples/toy/extensions/brian2/distributions.py) has NEST's `exponential` this way.

## Speed

Brian2 compiles the network's code before it runs. Three ways, from `backend_options` or the simulation file's `backend.options`:

| Option | Compiles | Runs | For |
| :--- | :--- | :--- | :--- |
| default (Cython) | about a minute the first time a kind of network runs; kept for later runs | on one thread | most runs |
| `codegen_target: numpy` | nothing, starts at once | slower | a quick look at a small network |
| `device: cpp_standalone` | about a minute at every run | fastest, on `local_num_threads` threads | long or large runs |

- With `cpp_standalone`, `standalone_directory: brian2_build` keeps the compiled code in that folder, and a later run there compiles only what changed. Two runs at the same time must not share the folder.
- The threads speed up the simulation; Brian2 creates the synapses on one thread.
- Without a compiler, the default falls back to numpy.
- The network is built from few Brian2 objects, since Brian2 spends time on each: the populations of one neuron model share a `NeuronGroup`, and all connections between two of them through the same synapse are one `Synapses`.
