# Builders (optional)

You can work without a builder: a network model is its files, so copy the toy's, edit them and run ([A new network model](new-network.md)). [Tutorial 4](tutorials/4_builder.md) shows a small builder at work.

A builder is your own code that writes those files for you. It is worth it when the numbers come from somewhere else:

| Your model has | A builder can |
| :--- | :--- |
| tables from a paper or a dataset | read them, in whatever form they come |
| connection probabilities, PSP amplitudes | turn them into what the simulator takes: synapse numbers, currents in pA |
| many populations or areas | write hundreds of connections without typing them |
| variants | write each one as a folder of its own: a scaled copy, another background input |

The model's decisions then live in one place, your code, and the files show their result.

## Anything that writes the files

There is no class to inherit and no function to fill in. A builder can be a script, a notebook, a package with its own interface, or a program in another language: what counts is the files it writes. The core checks them when it reads them, so a mistake shows up at once, naming the file and the field:

```bash title="Terminal"
microcircuit-lab run --network my_model      # checks, then simulates
```

```python
from microcircuit_lab import read_network
read_network("configs/network/my_model")     # checks only
```

The format of every file: [Configuration files](config_files.md).

## A small builder

This one writes a two-population network. It uses `write_network_directory` (optional), which writes every file of the folder and checks it:

```python
# builders/two_populations/__init__.py
from microcircuit_lab.builder_tools import write_network_directory


def main(argv=None):
    background = {"rate": 8.0, "indegree": 1000, "weight": {"value": 87.8, "unit": "pA"}, "delay": {"value": 1.5}}
    write_network_directory(
        "configs/network/two_populations",
        populations=[{"name": "E", "size": 800, "neuron": "lif"},
                     {"name": "I", "size": 200, "neuron": "lif"}],
        neurons={"lif": {"model": "iaf_psc_exp", "parameters": {"C_m": 250.0, "tau_m": 10.0, "V_th": -50.0}}},
        connections=[{"source": "E", "target": "I", "n_synapses": 16000,
                      "weight": {"value": 87.8, "unit": "pA"}, "delay": {"value": 1.5}},
                     {"source": "I", "target": "E", "n_synapses": 16000,
                      "weight": {"value": -351.2, "unit": "pA"}, "delay": {"value": 0.75}}],
        poisson_background={"E": background, "I": background},
    )
```

```bash title="Terminal"
microcircuit-lab generate two_populations    # runs main(): writes configs/network/two_populations/
microcircuit-lab run --network two_populations
```

## Running it with `microcircuit-lab generate` (optional)

You can run a builder however you like (`python my_builder.py`, a notebook cell, a button in your interface). `microcircuit-lab generate <name>` is a shortcut that needs two things:

- a folder `builders/<name>/` in your project, with an `__init__.py`;
- a function `main(argv=None)` in it. `generate <name> --any --options` passes the options on as `argv`.

`microcircuit-lab generate` with no name lists the builders it finds. A builder in an installed package can register under the `microcircuit_lab.builders` entry-point group instead (see `microcircuit_lab/project_code.py`).

## Helpers (optional)

| Helper | What it does |
| :--- | :--- |
| `microcircuit-lab new-builder my_model` | writes `builders/my_model/` with a working example to start from |
| `write_network_directory` | writes every file of a network folder, with every value stated (defaults included), and checks it |
| `weight`, `delay`, `zero_bound` | write a weight or delay entry: fixed, or drawn with a relative spread and a bound ([Weights and delays](weights-and-delays.md)) |
| `num_synapses_from_conn_prob` | a connection probability to a number of synapses |
| `psp_to_psc_iaf_psc_exp`, `psc_to_psp` | a PSP amplitude (mV) to a current (pA), and back |
| `scale_network` | a smaller copy of a network model ([Scaling a network model](scaling.md)) |
| `replace_background_by_mean_current` | the Poisson background replaced by its mean current ([Background input](network-files.md#background-input)) |

All are in `microcircuit_lab.builder_tools`, with their arguments in [Python API](api.md#builder-tools). Use the ones that help.

## Examples

The examples' builders, from small to large: [toy](https://github.com/shimoura/microcircuit-lab/tree/main/examples/toy/builders/toy) (one short file), [pd14](https://github.com/shimoura/microcircuit-lab/tree/main/examples/pd14/builders/pd14) (the parameters with their sources, then the conversions), [jiang24](https://github.com/shimoura/microcircuit-lab/tree/main/examples/jiang24/builders/jiang24) and [humam](https://github.com/shimoura/microcircuit-lab/tree/main/examples/humam/builders/humam) (data files, many areas). Each example's README says what its builder takes from the publication.
