# 4 · A builder

Let code write the YAML files when the numbers come from a paper. About ten minutes, in the project of [tutorial 1](1_first_run.md).

[Tutorial 3](3_own_network_model.md) wrote a network model by hand, and for many models that is all it takes. But a paper gives a model as tables (connection probabilities, PSP amplitudes in mV), while the files hold what the simulator takes (synapse numbers, currents in pA). With two layers of E and I neurons, that is 4 populations and 16 connections to work out. A builder does it from the tables, and the next change is one number.

## The builder

A builder is a folder `builders/<name>/` with a function `main`. Write this one in `builders/two_layers/__init__.py`:

```python title="builders/two_layers/__init__.py"
"""Two layers, each with an excitatory and an inhibitory population, from a table of
connection probabilities and PSP amplitudes, as a paper would give them."""

from microcircuit_lab.builder_tools import (
    num_synapses_from_conn_prob,
    psp_to_psc_iaf_psc_exp,
    write_network_directory,
)

SIZES = {"L23_E": 400, "L23_I": 100, "L4_E": 400, "L4_I": 100}

# Connection probability, from the population of the column to that of the row.
PROBABILITY = {
    #          from L23_E  L23_I  L4_E   L4_I
    "L23_E": {"L23_E": 0.1, "L23_I": 0.1, "L4_E": 0.05, "L4_I": 0.0},
    "L23_I": {"L23_E": 0.1, "L23_I": 0.1, "L4_E": 0.05, "L4_I": 0.0},
    "L4_E": {"L23_E": 0.0, "L23_I": 0.0, "L4_E": 0.1, "L4_I": 0.1},
    "L4_I": {"L23_E": 0.0, "L23_I": 0.0, "L4_E": 0.1, "L4_I": 0.1},
}

PSP = {"E": 0.15, "I": -0.6}       # mV, by the source's cell type
DELAY = {"E": 1.5, "I": 0.8}       # ms
NEURON = {"C_m": 250.0, "tau_m": 10.0, "tau_syn_ex": 0.5, "tau_syn_in": 0.5,
          "E_L": -65.0, "V_reset": -65.0, "V_th": -50.0, "t_ref": 2.0}


def main(argv=None):
    connections = []
    for target, row in PROBABILITY.items():
        for source, p in row.items():
            if p == 0.0:
                continue
            cell_type = source[-1]
            tau_syn = NEURON["tau_syn_ex"] if cell_type == "E" else NEURON["tau_syn_in"]
            current = psp_to_psc_iaf_psc_exp(PSP[cell_type], NEURON["C_m"], NEURON["tau_m"], tau_syn)
            connections.append({
                "source": source,
                "target": target,
                "n_synapses": num_synapses_from_conn_prob(p, SIZES[source], SIZES[target]),
                "weight": {"value": current, "unit": "pA"},
                "delay": {"value": DELAY[cell_type]},
            })

    background = {"rate": 8.0, "indegree": 1000, "weight": {"value": 87.8, "unit": "pA"}, "delay": {"value": 1.5}}
    write_network_directory(
        "configs/network/two_layers",
        populations=[{"name": name, "size": size, "neuron": "lif"} for name, size in SIZES.items()],
        neurons={"lif": {"model": "iaf_psc_exp", "parameters": NEURON}},
        connections=connections,
        poisson_background={name: background for name in SIZES},
    )
```

- The model's numbers are at the top, as in the paper; the loop turns them into files.
- `num_synapses_from_conn_prob` and `psp_to_psc_iaf_psc_exp` do the two conversions; `write_network_directory` writes the folder and checks it. Use them if they help ([Builders](../builders.md#helpers-optional)): any code that writes the files works.

## Generate and run

```bash title="Terminal"
microcircuit-lab generate two_layers
```

It prints nothing when all goes well. The files are in `configs/network/two_layers/`, with the numbers worked out ([Weights and delays](../weights-and-delays.md) shows the PSP-to-current conversion):

```yaml title="configs/network/two_layers/connectivity.yaml (two of its ten lines)"
- {source: L4_E, target: L23_E, rule: fixed_total_number, n_synapses: 8207, weight: {value: 87.80849352920843, unit: pA}, delay: {value: 1.5}}
- {source: L4_E, target: L23_I, rule: fixed_total_number, n_synapses: 2052, weight: {value: 87.80849352920843, unit: pA}, delay: {value: 1.5}}
```

```bash title="Terminal"
microcircuit-lab run --network two_layers --simulation toy
```

```text title="Output"
L23_E   N=  400  spikes=   9850  rate=  24.625 Hz
L23_I   N=  100  spikes=   2517  rate=  25.170 Hz
L4_E    N=  400  spikes=   7457  rate=  18.642 Hz
L4_I    N=  100  spikes=   1855  rate=  18.550 Hz
```

L2/3 fires faster than L4: it gets the input from L4 on top of its own.

## Change one number

Make the connection from L4 to L2/3 twice as likely: in `PROBABILITY`, change the two `"L4_E": 0.05` to `0.1`. Generate and run again:

```bash title="Terminal"
microcircuit-lab generate two_layers
microcircuit-lab run --network two_layers --simulation toy
```

```text title="Output"
L23_E   N=  400  spikes=  12529  rate=  31.323 Hz
L23_I   N=  100  spikes=   3139  rate=  31.390 Hz
L4_E    N=  400  spikes=   7371  rate=  18.427 Hz
L4_I    N=  100  spikes=   1849  rate=  18.490 Hz
```

The builder worked out the new synapse numbers of both connections (16858 and 4214); L2/3 now fires at about 31 spikes/s. The decisions live in one place, the code, and the files show their result.

## More

- What else a builder can be (a script, a notebook, your own interface) and the helpers: [Builders](../builders.md).
- `microcircuit-lab new-builder my_model` writes a commented builder to start from.
- The examples' builders, from a table of a paper to many areas: [PD14](https://github.com/shimoura/microcircuit-lab/tree/main/examples/pd14/builders/pd14), [HuMAM](https://github.com/shimoura/microcircuit-lab/tree/main/examples/humam/builders/humam).

Next: [5 · A parameter sweep](5_parameter_sweep.ipynb), in Python.
