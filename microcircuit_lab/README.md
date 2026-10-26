# Microcircuit Lab

Build, simulate and analyse spiking neural network models, from a single microcircuit to multi-area models. A network is a folder of YAML files; the same core checks it, runs it in NEST or Brian2 and plots the result, whatever model it came from.

## Contents

- [Quick start](#quick-start)
- [How it works](#how-it-works)
- [Included networks](#included-networks)
- [Starting a project](#starting-a-project)
- [Installation](#installation)
- [Configuration](#configuration)
- [Scaling a network](#scaling-a-network)
- [Adding a new network](#adding-a-new-network)
- [Analysing a run](#analysing-a-run)
- [Running from a script](#running-from-a-script)
- [Run outputs](#run-outputs)
- [Using a NESTML model](#using-a-nestml-model)
- [Running with Brian2](#running-with-brian2)
- [Changing the core](#changing-the-core)
- [Adding a backend](#adding-a-backend)
- [Testing](#testing)

## Quick start

```bash
pip install "microcircuit_lab[nest] @ git+https://github.com/shimoura/microcircuit-lab"
microcircuit-lab init my_project --with-core
cd my_project
microcircuit-lab run --network toy
```

This runs `toy`, two populations (E and I), and saves the run in `output/toy/<timestamp>/`, with a raster, firing rates, power spectrum and ISI CV in `plots/`.

The same from Python:

```python
from microcircuit_lab import Simulation

simulation = Simulation.from_yaml(network_name="toy")
simulation.run()
```

Next:

- **Other settings** (duration, seed, threads, what to record): edit `configs/simulation/toy.yaml` and run again.
- **Parameter sweeps, several seeds, any batch:** a Python script that loops over runs; recipes in [Running from a script](#running-from-a-script).
- **Your own network:** [Adding a new network](#adding-a-new-network).

## How it works

![What you write, what the core does when you run it, and what you get](../docs/images/how_it_works.svg)

- **Builder** (optional): your code that turns published tables or other data into the YAML files. The only model-specific code.
- **Check**: every file and field is checked; a mistake names the file and the field.
- **Prepare**: each background rate per synapse becomes the rate of its Poisson generator (or a constant current, with `background_mode: mean_current`). Everything else is simulated as the files give it; a smaller network is a folder of its own ([Scaling a network](#scaling-a-network)).
- **Run folder**: everything a run produced. Plots can be redone from it without simulating again.

The files and functions behind each step, and where to look when something goes wrong: [docs/workflow.md](../docs/workflow.md).

<a id="included-models"></a>

## Included networks

| Network | What it is |
|---|---|
| `toy`, `toy_stimulated` | two populations (E and I), with and without stimuli; the smallest example |
| `toy_two_areas` | a made-up two-area network with different layers and cell types (E, PV, SOM, VIP) |
| `toy_two_areas_advanced` | the same network with the optional features on: values drawn per neuron, connection rules, synapse models, receptor ports |
| `pd14` | the Potjans & Diesmann (2014) microcircuit |
| `humam_single`, `humam_all` | the human multi-area model (Pronold et al. 2024): one area, or all 34 |

`pd14` is full scale (77,169 neurons, about 15 GB of memory) and simulates 11 s; for a quick look, run `pd14_downscaled` (N and K scaled by 0.1; see [Scaling a network](#scaling-a-network)). Each builder's README in `builders/` gives the model's sources.

## Starting a project

A project is your own folder, usually your own git repository:

```text
my_project/
├── builders/           your networks' builders
├── analyses/           your analyses
├── configs/            network, simulation and analysis configs
├── experiments/        your experiment scripts
├── extensions/         what you add to a simulator: neurons, synapses, connection rules, ...
├── output/             the runs (created by the first run)
└── microcircuit-lab/   with --with-core: your copy of the core
```

| Command | What you get |
|---|---|
| `microcircuit-lab init my_project` | the empty folders; the core stays installed in your Python environment |
| `microcircuit-lab init my_project --with-core` | the folders, the examples, and a copy of the core in `microcircuit-lab/` (installed editable) |

Then, for a model of your own:

```bash
cd my_project
microcircuit-lab new-builder my_model   # creates builders/my_model/
microcircuit-lab generate my_model      # writes configs/network/my_model/
microcircuit-lab run --network my_model
```

Good to know:

- Run the commands from the project folder; that is where `builders/`, `analyses/`, `configs/` and `extensions/` are looked for.
- With `--with-core`, the copy of the core is yours: change it and commit it with your project. Your edits take effect at once, and each run's `metadata.json` records your project's git commit, which then covers the core too.
- A later core release is not applied to the copy by itself; compare and merge it by hand if you want it. To propose a change to the original core, see [CONTRIBUTING.md](../CONTRIBUTING.md).
- The examples (every builder and config) are copied too, and are yours as well. A name that already exists is skipped, so `microcircuit-lab init . --with-core` is safe in an existing repository.

## Installation

```bash
pip install "microcircuit_lab[nest] @ git+https://github.com/shimoura/microcircuit-lab"
```

This installs the latest version. For a fixed one, add its tag from the [releases](https://github.com/shimoura/microcircuit-lab/releases) to the address: `...microcircuit-lab@<tag>`. Only NEST built from source runs on several MPI processes; the pip and conda-forge builds use threads only. Drop `[nest]` if you get NEST another way:

- conda-forge: `mamba install -c conda-forge nest-simulator`
- from source, e.g. on a cluster for MPI: see the [NEST installation docs](https://nest-simulator.readthedocs.io/en/stable/installation/index.html) and `scripts/install_nest_from_source.sh` (`NEST_WITH_MPI=ON` for MPI)

All that matters is that `import nest` works. Check the install with `microcircuit-lab --version`.

To run on Brian2 instead of NEST, install `[brian2]` (`pip install "microcircuit_lab[brian2] @ git+https://github.com/shimoura/microcircuit-lab"`); see [Running with Brian2](#running-with-brian2).

The power spectrum with `method: multitaper` needs `mne`: `pip install "microcircuit_lab[multitaper]"`.

To work on the core itself, clone the repository and install it editable:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,nest]"
```

## Configuration

```text
configs/
├── network/<name>/
│   ├── network.yaml             names the other files
│   ├── populations.yaml         sizes, neuron of each population
│   ├── neurons.yaml             neuron models and parameters
│   ├── connectivity.yaml        rules, synapse numbers, weights, delays
│   ├── synapses.yaml            optional: synapse models, receptor ports
│   ├── background_inputs.yaml   background Poisson input
│   ├── stimuli.yaml             optional: inputs for experiments
│   ├── scaling.yaml             only in a scaled network: how it was scaled
│   └── reference.yaml           optional: reference rates
├── simulation/<name>.yaml       duration, seed, threads, simulator, what to record
└── analysis/<name>.yaml         optional: which plots, time window, style
```

- **The fields** of every file, with units, limits and defaults: [docs/config_files.md](../docs/config_files.md), one commented example per file. `configs/network/toy/` is a small working example to copy.
- **Checks.** A mistake fails at once, naming the file and the field:
  ```text
  populations.yaml: populations.0.size: Input should be greater than 0
  ```
  `load_network("configs/network/<name>")` runs the whole check without simulating. A neuron's `parameters:` are the one block checked by the simulator, not here, since every neuron model takes different ones.
- **Units.** Every number in the files is in the package's units, whichever simulator runs it: mV, ms, pF, pA, nS, and spikes/s for rates.
- **Names the simulator looks up.** Some fields name something. The shared names run on every simulator; any other name is looked up by the simulator that runs the network, and one it doesn't have stops the run before anything is built, saying so:

  | Field | Shared | Any other name |
  |---|---|---|
  | `neurons.yaml` `model` | none | NEST: its own models and NESTML modules; Brian2: a `NeuronModel` in `extensions/brian2/` |
  | `synapses.yaml` `model` | `static_synapse` | NEST: its own models; Brian2: a `SynapseModel` in `extensions/brian2/` |
  | `rule` of a connection | `fixed_total_number`, `fixed_indegree`, `fixed_outdegree`, `pairwise_bernoulli`, `one_to_one`, `all_to_all` | with `parameters`; Brian2: a `ConnectionRule` in `extensions/brian2/` ([Connection rules of your own](#connection-rules-of-your-own)) |
  | `distribution` of a connection's weight or delay | `normal`, `uniform`, `lognormal`, `fixed` | with `parameters`; Brian2: a `Distribution` in `extensions/brian2/` ([Distributions of your own](#distributions-of-your-own)) |
  | `receptor_port` of a synapse | a number | NEST: a name in the target model's `receptor_types`; Brian2: the variable the connection adds to |

  A network that uses names of one simulator runs on that simulator only. What the core can't know about a name of your own, it doesn't guess: scaling a network with such a rule, or with weights from such a distribution, stops with an error.
- **Matched by name.** `microcircuit-lab run --network toy` uses `configs/simulation/toy.yaml` and `configs/analysis/toy.yaml`; `--simulation` and `--analysis` pick others. Both files are optional.

### Stimuli

```yaml
stimuli:
  - type: dc                 # a constant current, from start to stop
    targets: [E]
    amplitude: 200.0         # pA
    start: 500.0             # ms
    stop: 600.0

  - type: poisson            # a Poisson spike train
    targets: [E, I]
    rate: 50.0               # spikes/s
    start: 200.0
    stop: 400.0
    weight: {mean: 87.8, rel_std: 0.0, distribution: fixed, unit: pA}
    delay: {mean: 1.5, rel_std: 0.0, distribution: fixed}
```

- Types: `dc`, `poisson`, and `inhomogeneous_poisson` (a rate that changes in steps). [docs/config_files.md](../docs/config_files.md#stimuliyaml) lists their fields.
- Stimuli are applied exactly as written: not scaled, not compensated.
- They add to the background input and to each other: several entries give several pulses, with their own targets and times. Without `stop`, a stimulus lasts until the end of the run.
- Add `stimuli: stimuli.yaml` to `network.yaml`. A runnable example: `microcircuit-lab run --network toy_stimulated`.

### Background input

`background_inputs.yaml` is the always-on Poisson input of each population (rate per synapse × `background_indegree`).

- **`background_mode: mean_current`** (at the top of the file) replaces that Poisson input by its mean, a constant current: the same average drive, without the fluctuations, as in Potjans & Diesmann (2014), Fig. 5. It applies to every population, and needs weights in pA on the default receptor port. Example: `microcircuit-lab generate pd14 --network-name pd14_mean_current --background-mode mean_current`.
- **A constant current of your own** is not a background mode; it adds to whichever background you use. For the whole run, set `I_e` in a neuron entry (every population using that entry); for chosen populations or times, add `dc` stimuli (above).
- **`generator: <name>`** in an entry: populations that give the same name share one Poisson generator. Each neuron still gets its own independent spike train; only the number of generators changes, which saves memory when many populations have the same input. They need the same `rate`, `background_indegree` and `synapse`. The random draws differ from one generator each, so the spikes are statistically the same, not identical.

### Weights and delays

A weight's `mean` is what the simulator gets, and its `unit` (required) says what it is. Nothing is converted:

| `unit` | Meaning | Example model |
|---|---|---|
| `pA` | a current | `iaf_psc_exp` |
| `nS` | a conductance | `aeif_cond_exp` |
| `mV` | a jump of the membrane potential | `iaf_psc_delta` |

NEST can't check the unit; Brian2 checks it against the variable the weight adds to. A model that gives its weights as PSP amplitudes converts them in its builder, with the target's neuron parameters:

```python
from microcircuit_lab.builder_tools import psp_to_psc_iaf_psc_exp, weight

current = psp_to_psc_iaf_psc_exp(0.15, C_m=250.0, tau_m=10.0, tau_syn=0.5)   # 87.8 pA
weight(current, unit="pA", rel_std=0.1)
```

The formula holds for current-based LIF neurons with exponential synaptic currents (`iaf_psc_exp` and its variants); use `tau_syn_in` for an inhibitory weight. Keep the PSP in a comment next to the value if you write the file by hand, as `configs/network/toy/` does.

- **Out-of-range draws.** `bound_mode` at the top of `connectivity.yaml`: `redraw` (default) draws again a weight with the wrong sign or a delay below the minimum; `clip` sets it to the limit, as HuMAM does. The minimum delay is half the time step, or the delay's own `minimum`. Either way the drawn values no longer have exactly the `mean` you wrote, while the scaling compensation uses that `mean`: negligible for a small spread (`rel_std` 0.1), noticeable around `rel_std` 1.
- **Excitatory or inhibitory** input is told by the sign of the weight, never by a population's name.
- **Distributions.** A weight or delay is drawn from `normal` (default), `uniform`, `lognormal` or `fixed`, with its `mean` and `rel_std`, on every simulator. Any other name is a distribution of your own, with `parameters`, for the weights and delays of connections; for now Brian2 only (see [Distributions of your own](#distributions-of-your-own)).

### Connection rules and synapses

Each connection has a `rule` and the number that rule takes:

| `rule` | number | |
|---|---|---|
| `fixed_total_number` (default) | `n_synapses` | that many synapses in total |
| `fixed_indegree` | `indegree` | that many onto each target neuron |
| `fixed_outdegree` | `outdegree` | that many from each source neuron |
| `pairwise_bernoulli` | `p` | each pair connected with probability `p` |
| `one_to_one` | none | the k-th source neuron to the k-th target neuron (populations of the same size) |
| `all_to_all` | none | every pair |

These rules run on every simulator. Any other name, with `parameters` instead of a number, is looked up by the simulator: on NEST one of its own rules (e.g. `rule: pairwise_poisson, parameters: {pairwise_avg_num_conns: 2}`), on Brian2 a rule of your own (see [Connection rules of your own](#connection-rules-of-your-own)).

Scaling keeps each neuron's share of synapses whatever the rule (`p` grows when the populations shrink). Three cases can't keep it, and stop with an error: `one_to_one` with `K_scaling` other than 1 (each neuron always gets one input), `all_to_all` with `K_scaling` different from `N_scaling` (each neuron gets the whole source population), and any other rule. `allow_autapses` and `allow_multapses` are passed to the simulator if given; left out, both are allowed.

A connection, background input or Poisson stimulus can name a synapse from `synapses.yaml` (add `synapses: synapses.yaml` to `network.yaml`); without one it uses the simulator's `static_synapse` on the default port:

```yaml
synapses:
  ampa: {model: static_synapse, receptor_port: 1}
  nmda: {model: static_synapse, receptor_port: 2}
  depressing: {model: tsodyks2_synapse, parameters: {U: 0.5, tau_rec: 800.0}}
```

```yaml
connections:
  - {source: E, target: E, rule: pairwise_bernoulli, p: 0.1, synapse: ampa, weight: {...}, delay: {...}}
  - {source: E, target: E, rule: pairwise_bernoulli, p: 0.1, synapse: nmda, weight: {...}, delay: {...}}
```

- A pair can have one entry per synapse, as above.
- A port can also be given by name (`receptor_port: AMPA`), which the simulator resolves: NEST looks it up in the `receptor_types` of the target's neuron model (e.g. `ht_neuron`), Brian2 takes it as the variable the connection adds to.
- The core knows the time constants of the default port only (`tau_syn_ex`, `tau_syn_in`). The input lost by scaling is compensated only for weights in pA on the default port, not for other units (e.g. conductances) or other ports; a warning lists those connections. A neuron with several ports (e.g. `iaf_psc_exp_multisynapse`) takes its time constants as a list: `tau_syn: [0.5, 100.0]`. Such a neuron may have no default port at all, so its background input needs a `synapse` too.
- With a plastic synapse, the scaling compensation uses the initial weights. With short-term plasticity (`tsodyks2_synapse`, ...) each spike transmits weight × u × x, so a weight converted from a PSP gives that PSP at u·x = 1: with U = 0.5 the first spike gives half of it.
- A runnable example with all of this, and values drawn per neuron: `microcircuit-lab run --network toy_two_areas_advanced` ([builders/toy_two_areas](../builders/toy_two_areas/README.md#advanced-variant)).

### Large files

A builder writes long tables (`connectivity.yaml` of a multi-area model) one record per line, `- {source: ..., target: ..., weight: {...}, ...}`: `humam_all` has about 8,400 lines instead of 100,000. It is plain YAML and loads like any other. `write_network_directory` does this for you.

For millions of connections, YAML gets slow to write and read. `connectivity.yaml` can then name a CSV file instead of listing the rows:

```yaml
bound_mode: redraw
connections_file: connections.csv
```

The CSV has one row per connection and the same fields, with nested names joined by a dot (`weight.mean`, `delay.rel_std`); columns with a default can be left out. It opens in a spreadsheet. `write_network_directory` writes it when given a `ConnectionTable` (`config/connection_table.py`), and a run with more than 20,000 connections saves its prepared connections the same way, next to `config.yaml`.

## Scaling a network

A full-scale network can be slow or need a lot of memory. A smaller copy is a network folder of its own, with the scaled numbers in its files, so what you read is what is simulated:

```bash
microcircuit-lab generate pd14 --n-scaling 0.1 --k-scaling 0.1 --network-name pd14_downscaled
microcircuit-lab run --network pd14_downscaled
```

`--n-scaling 0.1` keeps 10 % of the neurons, `--k-scaling 0.1` 10 % of the inputs of each neuron. The builder calls `scale_network` and writes the result; the folder's `scaling.yaml` records how it was made, and is never applied:

```yaml
# configs/network/pd14_downscaled/scaling.yaml
scaled_from: pd14
scaled_with: microcircuit_lab.builder_tools.scaling.scale_network
parameters:          # the function's own arguments
  N_scaling: 0.1
  K_scaling: 0.1
  preserve_mean_input: true
  preserve_variance: true
  compensate_recurrent_input: true
```

From a script (a network without a builder, a sweep over the factors, other options), call it yourself:

```python
from microcircuit_lab import Simulation, read_network
from microcircuit_lab.builder_tools import scale_network, write_network
from microcircuit_lab.config.simulation import SimulationConfig

full = read_network("configs/network/toy")
small = scale_network(full, N_scaling=0.5, K_scaling=0.5, scaled_from="toy", compensate_recurrent_input=False)
write_network(small, "configs/network/toy_half")                       # a folder, or:
Simulation(small, SimulationConfig(t_sim=1000.0), network_name="toy_half").run()   # each run folder keeps the scaled numbers
```

Other scaling rules: copy `scale_network` (`builder_tools/scaling.py`) into your project, e.g. `builders/common/scaling.py`, change it, and call your copy; its record names it in `scaled_with` (`f"{__name__}.scale_network"`), with its own `parameters`. A function of your own builds the record the same way: `ScalingRecord(scaled_from=..., scaled_with=f"{__name__}.my_scaling", parameters={...})` (`config/scaling.py`), set as the network's `scaling`. A scaled network can't be scaled again (its currents aren't the full input): scale the full one with the product of the factors.

`N_scaling` only makes the populations smaller: each neuron keeps all its inputs. `K_scaling` cuts the inputs, and that changes the input current each neuron gets. With $K$ inputs of weight $J$ (pA) firing at rate $\nu$ (spikes/ms), and synaptic time constant $\tau_s$, the mean and the variance of that current are

$$\mu = \tau_s\, K J \nu, \qquad \sigma^2 = \tfrac{1}{2}\,\tau_s\, K J^2 \nu .$$

With $K \to k K$ ($k$ = `K_scaling`), the weights alone can keep $\mu$ or $\sigma^2$, not both. Scaling the weights by $1/\sqrt{k}$ and adding the lost mean as a DC current keeps both (van Albada, Helias & Diesmann 2015, *PLoS Comput Biol* 11:e1004490). The options choose what to keep:

| `scale_network` | Weights | DC added | Mean $\mu$ | Fluctuations $\sigma^2$ |
|---|---|---|---|---|
| defaults | $J/\sqrt{k}$ | $(1-\sqrt{k})\,\mu$ | kept | kept |
| `compensate_recurrent_input=False` | $J/\sqrt{k}$ | for the background input only | recurrent part lower | kept |
| `preserve_mean_input=False` | $J/\sqrt{k}$ | none | lower: $\sqrt{k}\,\mu$ | kept |
| `preserve_variance=False` | $J/k$ | none | kept | larger: $\sigma^2/k$ |

- The DC is added to each population's `I_e` in the scaled files (a population gets a neuron entry of its own when its current differs from the others'). `I_e` is sent to the simulator only when a neuron entry sets it or a DC is added, so a model without `I_e` works when it needs no DC; when it does, the run stops with an error naming it.
- The DC for the recurrent input needs the full-scale rate $\nu$ of every population, `full_mean_rates` in `reference.yaml`; without them, scaling stops with an error. `compensate_recurrent_input=False` compensates the background input only, and needs no rates.
- The DC is known only for weights in pA on the default receptor port; another unit (e.g. nS) or port stops the scaling with an error, unless `preserve_mean_input=False`.
- With `background_mode: mean_current`, the run computes the background current from the scaled background, and the DC adds the lost part, so together they are the full-scale mean.
- Excitatory and inhibitory inputs each use their own $\tau_s$ (`tau_syn_ex`, `tau_syn_in`).
- These are the mean and variance only. A scaled network is close to the full one, not equal: PD14 at $k = 0.1$ has most rates within 10–20 %, and L2/3 E lower (0.5 instead of 0.9 spikes/s).
- A connection left with less than one synapse is dropped.

<a id="adding-a-new-model"></a>

## Adding a new network

![Two ways to add a model: write the YAML files, or write a builder that writes them](../docs/images/new_model.svg)

The core never changes for a new network.

### Option A: write the YAML yourself

For a new idea, or a model small enough to write by hand.

```bash
cp -r configs/network/toy configs/network/my_model
# edit the files
microcircuit-lab run --network my_model
```

Loading checks every file; fix what it reports. Add `configs/simulation/my_model.yaml` for the duration, threads and recording, or the defaults are used (with a warning).

### Option B: write a builder

For a model whose parameters come from data (published tables, recordings, matrices).

```bash
microcircuit-lab new-builder my_model   # builders/my_model/__init__.py, with a working example
microcircuit-lab generate my_model      # runs it: writes configs/network/my_model/
```

Replace the example values with your model's. The builder hands its parts to `write_network_directory`, which writes and checks every file:

```python
from microcircuit_lab.builder_tools import delay, weight, write_network_directory

write_network_directory(
    "configs/network/my_model",
    populations=[...],
    neurons={...},
    connections=[{"source": "E", "target": "I", "n_synapses": 5000,
                  "weight": weight(87.8, unit="pA", rel_std=0.1),
                  "delay": delay(1.5, rel_std=0.5)}, ...],
    background_inputs={...},
)
```

- A builder is found by its folder `builders/<model>/` with a `main(argv=None)`; there is no list to edit. `microcircuit-lab generate` with no name lists what it found.
- `builder_tools` also has `num_synapses_from_conn_prob` and `psp_to_psc_iaf_psc_exp`.
- `write_network_directory` is optional: files written any other way are checked the same way when loaded.
- Worked examples: `builders/pd14/`, `builders/toy_two_areas/`, `builders/humam/`. Add a `README.md` with your model's sources.
- A builder in another installed package can register under the `microcircuit_lab.builders` entry-point group (see `microcircuit_lab/project_code.py`).

## Analysing a run

### Re-plot without simulating again

```bash
microcircuit-lab run --network toy                                          # prints "Run directory: ..."
microcircuit-lab run --run-dir output/toy/<timestamp> --begin 200 --end 400
```

`--run-dir` takes the same flags as `--network`. The plots go back into the run's `plots/`.

Which plots are made, and how they look, is set in `configs/analysis/<name>.yaml`; every setting is in [docs/config_files.md](../docs/config_files.md#analysisnameyaml).

### Use the bundled functions

```python
from microcircuit_lab import Simulation
from microcircuit_lab.analysis import compute_population_firing_rates, plot_firing_rates

simulation = Simulation.from_run_dir("output/toy/<timestamp>")   # opens the run, no simulation
rates = compute_population_firing_rates(simulation, begin=200.0)
plot_firing_rates(simulation, begin=200.0)
```

- Plots: `plot_raster`, `plot_firing_rates`, `plot_power_spectrum`, `plot_isi_cv`.
- Numbers: `compute_*` for rates, ISI CV, power spectrum and deviation from the reference rates.
- Multi-area networks: pass `area="V1"`; `list_areas(simulation)` gives the names.

### Your own analysis: any script

There are no rules: open a run folder and do what you want.

```python
# my_analysis.py
import sys

from microcircuit_lab import Simulation
from microcircuit_lab.analysis import compute_population_firing_rates

simulation = Simulation.from_run_dir(sys.argv[1])
print(compute_population_firing_rates(simulation, begin=200.0))

events = simulation.backend.get_spike_events("E")   # {"senders": ..., "times": ...}
```

```bash
python my_analysis.py output/toy/<timestamp>
```

- Read data through `simulation` (`backend.get_spike_events`, `network`, `simulation_config`).
- Keep the script anywhere, e.g. in `experiments/`. In `analyses/`, put its work under `if __name__ == "__main__":`, because `microcircuit-lab run` imports every file there.
- To list a file you saved in the run's `metadata.json`: `register_artifact(simulation.output_dir, "plots", path)` from `microcircuit_lab.run_folder`.

### Optional: let `microcircuit-lab run` make your plot

Register a function in a file in `analyses/`, and the command gets a flag for it:

```python
# analyses/rate_bars.py
import matplotlib.pyplot as plt

from microcircuit_lab.analysis import compute_population_firing_rates, register_plot


def rate_bars(simulation, save_path, area=None):
    rates = compute_population_firing_rates(simulation, area=area)
    fig, ax = plt.subplots()
    ax.bar(list(rates), list(rates.values()))
    fig.savefig(save_path)


register_plot("rate_bars", rate_bars)
```

```bash
microcircuit-lab run --run-dir output/toy/<timestamp> --rate-bars
```

The figure is saved in `plots/`, one per area with `--area all`, and listed in `metadata.json`. The first parameter is the simulation; name only what else you need, and the command fills it in:

| Parameter | What you get |
|---|---|
| `save_path` | where to save the figure |
| `area` | one area name, or `None` for single-area networks |
| `begin`, `end` | the time window in ms |
| `style` | the shared plot style |
| `config` | the `rate_bars:` section of the analysis file, as a dict |
| `show` | `True` with `--show` |
| `show_reference` | `True` with `--reference` |

- Any other parameter needs a default.
- The plot is off by default: pass `--rate-bars`, or set `enabled: true` in its section of the analysis file.
- A name already taken (`raster`, ...) raises an error.
- A package can provide such plots through the `microcircuit_lab.analyses` entry-point group (see `microcircuit_lab/analysis/run_command_plots.py`).

## Running from a script

The command and a script run the same steps (check, prepare, simulate, save); the command also makes the plots.

| | Command | Script |
| :--- | :--- | :--- |
| run a network as configured | `microcircuit-lab run --network toy` | `Simulation.from_yaml(network_name="toy").run()` |
| change a setting (seed, duration, ...) | edit `configs/simulation/toy.yaml` | change it in code, below |
| change the network | edit its YAML files | `read_network`, change, `prepare_network`, below |
| many runs (seeds, a sweep) | a shell loop | a Python loop, below |
| plots | made from `configs/analysis/toy.yaml` | call the plot functions, or `run --run-dir <folder>` afterwards |

Scripts go in your project's `experiments/` and run from the project folder (`python experiments/my_sweep.py`), so that `configs/` and `output/` are found. A worked example: `experiments/toy/background_drive_sweep.py`.

**Other settings.** The settings are a `SimulationConfig` (fields: [docs/config_files.md](../docs/config_files.md)); replace it before `run()`:

```python
from microcircuit_lab import Simulation

simulation = Simulation.from_yaml(network_name="toy")
settings = simulation.simulation_config
simulation.simulation_config = settings.model_copy(update={"t_sim": 2000.0, "rng_seed": 7})
simulation.run()
print(simulation.output_dir)   # where this run was saved
```

The simulator is part of these settings (`backend`), so a new `SimulationConfig` runs on its own `backend` (NEST if not set), not on the one given to `from_yaml`. `model_copy` keeps it.

**A batch.** Each run is independent (the simulator starts afresh) and gets its own `<timestamp>` folder. The folder is the simulation file's `output_dir`, or `output/<network>` if it has none; give each group of runs its own:

```python
from microcircuit_lab import Simulation
from microcircuit_lab.analysis import compute_population_firing_rates

rates = {}
for seed in (1, 2, 3):
    simulation = Simulation.from_yaml(network_name="toy")
    settings = simulation.simulation_config
    output = settings.output.model_copy(update={"output_dir": f"output/toy_seeds/seed_{seed}"})
    simulation.simulation_config = settings.model_copy(update={"rng_seed": seed, "output": output})
    simulation.run()
    rates[seed] = compute_population_firing_rates(simulation)   # {population: spikes/s}
```

**A changed network.** `read_network` gives the network as written; change it, then `prepare_network` gets it ready to simulate:

```python
from microcircuit_lab import Simulation, prepare_network, read_network
from microcircuit_lab.config.simulation import SimulationConfig

network = read_network("configs/network/toy")
populations = {name: pop.model_copy(update={"background_indegree": 2000})
               for name, pop in network.populations.items()}
network = prepare_network(network.model_copy(update={"populations": populations}))

simulation = Simulation(network, SimulationConfig(t_sim=1000.0), network_name="toy_k2000")
simulation.run()
```

**Results and plots.** The functions in `microcircuit_lab.analysis` take a simulation, just run or reopened later:

```python
from microcircuit_lab.analysis import plot_raster

plot_raster(simulation, save_path=simulation.output_dir / "plots" / "raster.png", show=False)
later = Simulation.from_run_dir("output/toy_seeds/seed_1/<timestamp>")   # no simulator needed
```

Runs in one script go one after another. For runs in parallel, start several scripts; each run still gets its own folder. With several MPI processes, save or plot only where `simulation.is_main_process` is true (see [Several MPI processes](#several-mpi-processes)).

## Run outputs

```text
output/<network>/<timestamp>/
├── recordings/     spikes (and voltages), written by the simulator
├── plots/          made by microcircuit-lab run
├── config.yaml     the prepared network and the simulation settings used
└── metadata.json   versions (core, simulator), git commits, MPI processes, spike counts, list of files
```

- Each run gets its own folder. `output.overwrite: true` in the simulation file reuses one.
- NEST writes `spikes-<id>-<thread>.dat` straight to disk, one file per thread; Brian2 keeps the spikes in memory and writes `spikes.csv` (and `voltage.csv`) at the end. `simulation.backend.get_spike_events(population)` reads them back.
- Voltages (`recording.voltage_recording: true`) are recorded for 5 neurons per population by default (`recording.voltage_sample_size`; `null` for all).

### Several MPI processes

```bash
mpirun -n 4 microcircuit-lab run --network pd14
```

- Needs NEST built from source with MPI (above), on a cluster against the cluster's MPI. Brian2 runs in one process.
- NEST spreads the neurons over the processes. Each process writes its own spike files into the same `recordings/` folder, so the processes must share a file system.
- The first process picks the run folder; when all have finished simulating, it alone prints the rates and writes `config.yaml`, `metadata.json` and the plots.
- In your own script, save or plot only where `simulation.is_main_process` is true.

## Using a NESTML model

1. Write the model in `extensions/nestml/` (e.g. `extensions/nestml/my_lif.nestml`), and compile it once:
   ```python
   from pynestml.frontend.pynestml_frontend import generate_nest_target

   generate_nest_target(input_path="extensions/nestml/my_lif.nestml",
                        target_path="extensions/nestml/build/my_module", module_name="my_module")
   ```
2. Use it in `neurons.yaml` like any model, by the name NESTML gives it (e.g. `my_lif_nestml`), with weights in the unit of the variable they add to (see [Weights and delays](#weights-and-delays)).
3. Load the module when running:
   ```python
   simulation = Simulation.from_yaml(
       network_name="toy_nestml",
       backend_options={"nest_modules": ["my_module"]},
   )
   ```
   or `microcircuit-lab run --network toy_nestml --nest-modules my_module`, or in the simulation file:
   ```yaml
   backend:
     name: nest
     options:
       nest_modules: [my_module]
   ```

Don't commit the compiled output; it depends on the platform and the NEST version.

## Running with Brian2

The same config files run on [Brian2](https://brian2.readthedocs.io): install it with `pip install -e ".[brian2]"`, then

```bash
microcircuit-lab run --network toy --backend brian2
```

or `Simulation.from_yaml(network_name="toy", backend="brian2")`. With `--brian2-device cpp_standalone` (`backend_options={"device": "cpp_standalone"}`) the network is compiled to C++ and runs with the simulation's `local_num_threads`.

A simulation file can choose the simulator and its options itself, so a profile such as `configs/simulation/toy_brian2.yaml` runs the same network on Brian2 (`--simulation toy_brian2`):

```yaml
backend:
  name: brian2                 # default: nest
  options:                     # passed to the backend as-is
    device: cpp_standalone
```

`--backend`, the `--brian2-...` flags and the `backend`/`backend_options` arguments override it. The options belong to the simulator named with them: with `--backend nest`, a Brian2 profile's options are left out. The run's `config.yaml` records the simulator and options used.

Brian2 has no neuron models of its own, so the core holds none: each model that `neurons.yaml` and `synapses.yaml` name is a `NeuronModel` or `SynapseModel` (`microcircuit_lab/backends/brian2/models.py`) in a Python file in `extensions/brian2/` of your project, or in a module given with `--extensions`. A name it cannot find is an error that says so, before anything is built. This repository's [`extensions/brian2/`](../extensions/brian2/) has the NEST models the example networks use, `static_synapse` is built in, and `init --with-core` copies them into a project.

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

- Values in the config files and in `defaults` are in the package's [units](#configuration) (mV, ms, pF, pA, nS, Hz); the equations use Brian2's.
- Every parameter is declared in the equations. A parameter in `neurons.yaml` that the model does not have, or one with no value, is an error.
- `I_e` is needed only where `neurons.yaml` sets it or scaling adds its compensation current to it; a model that declares it gives it a default (0.0). `I_stim` is the current of `dc` stimuli.
- A connection adds its weight to `excitatory` or `inhibitory`, as its sign says, or to `receptor_port` (e.g. `"I_syn_{port}"`) if its synapse has a `receptor_port`; a port given by name is that variable (e.g. `g_ampa`). A weight onto a conductance adds its size, as in NEST.
- A list parameter such as `tau_syn: [0.5, 2.0]` sets `tau_syn_1` and `tau_syn_2`; `equations` can be a function of the parameters when their number varies (see `iaf_psc_exp_multisynapse.py`).
- A `SynapseModel` takes Brian2's own forms. `model` holds the synapse's variables (the weight `w_syn` is added), `on_pre` and `on_post` are code or a dict of pathways to code (`{target}` is the variable the connection adds to), `delays` gives an expression for the delay of each pathway other than `pre` (the connection's delay sets `pre`), and `method` is the integration method. A summed variable such as `I_gap_post = g_gap*(V_m_pre - V_m_post) : amp (summed)` makes a gap junction (with `on_pre=""`; the target neuron declares `I_gap`, with a default). `extensions/brian2/` has no NEST-matching `stdp_synapse`: write a model of your own; NEST's `stdp_synapse` parameters are not mapped.

```python
stdp = SynapseModel(
    name="stdp",
    model="dapre/dt = -apre/tau_plus : 1 (event-driven)\ndapost/dt = -apost/tau_minus : 1 (event-driven)\n"
    "tau_plus : second (constant)\ntau_minus : second (constant)\nw_max : amp (constant)",
    on_pre="{target} += w_syn\napre += 0.01\nw_syn = clip(w_syn + apost*pA, 0*pA, w_max)",
    on_post="apost -= 0.012\nw_syn = clip(w_syn + apre*pA, 0*pA, w_max)",
    defaults={"tau_plus": 20.0, "tau_minus": 20.0, "w_max": 100.0},
)
```

### Connection rules of your own

A `rule` that is not one of the shared rules is a `ConnectionRule` in `extensions/brian2/` (or in a module given with `--extensions`). Its `condition`, `p` and `n` are the arguments of Brian2's `Synapses.connect`, as Brian2 expressions: which pairs may connect, the probability that such a pair does, and how many synapses it gets. They can use the connection's `parameters`, the neurons' variables (`V_m_pre`, `V_m_post`), and `index_pre` / `index_post`, each neuron's index within its population:

```python
# extensions/brian2/rules.py
from microcircuit_lab.backends.brian2.models import ConnectionRule

ring = ConnectionRule(name="ring", condition="abs(index_pre - index_post) <= width", p="p0")
```

```yaml
# connectivity.yaml
- {source: E, target: E, rule: ring, parameters: {width: 10, p0: 0.5}, allow_autapses: false, weight: {...}, delay: {...}}
```

In a CSV connection table, `parameters` is a column of JSON text (`"{""width"": 10, ""p0"": 0.5}"`). Scaling a network with such a rule stops with an error, since the core can't know how the rule scales (scale it in its builder instead).

### Distributions of your own

A weight or delay `distribution` that is not a shared one is a `Distribution` in `extensions/brian2/`: a Brian2 `expression` for each synapse's value, in the package's units (pA or nS for a weight, ms for a delay). It can use the connection's `mean` and `rel_std`, its `parameters`, the neurons' variables and `index_pre` / `index_post`:

```python
# extensions/brian2/distributions.py
from microcircuit_lab.backends.brian2.models import Distribution

decay = Distribution(name="decay", expression="mean * exp(-abs(index_pre - index_post) / length)", redraw_rounds=0)
```

```yaml
# connectivity.yaml
- {source: E, target: E, rule: fixed_indegree, indegree: 100,
   weight: {mean: 87.8, rel_std: 0, unit: pA, distribution: decay, parameters: {length: 20}}, delay: {...}}
```

- `mean` is still required: its sign says whether the weight is excitatory or inhibitory, and the expression gets it.
- A weight of the other sign than `mean`, or a delay below the minimum, is past its bound. How often it crosses it can't be known from an expression, so the definition says what to do: with `bound_mode: redraw` (the default), the value is drawn again `redraw_rounds` times and then clipped to the bound (0 clips at once); a definition without `redraw_rounds` stops the run before the build, unless `bound_mode: clip`.
- Scaling a network with weights from such a distribution stops with an error: the compensation needs the weights' real mean, which the core can't know. Delays are fine, since scaling leaves them alone. Background inputs and stimuli take the shared distributions only.

Brian2 spends time on every object it has, so the network is built from few: the populations of a neuron model share one `NeuronGroup`, and all connections between two of them through the same synapse are one `Synapses`, however many rows the connection table has. The default device runs on one thread. It compiles the network's code with Cython (Brian2's default, or numpy if there is no compiler): that takes a minute or so the first time a kind of network runs, and the compiled code is kept for later runs, also of the same network with other numbers. `backend_options={"codegen_target": "numpy"}` compiles nothing, so it starts at once but runs slower; worth it for a quick look at a small network. `cpp_standalone` compiles the whole network for a minute or so at every run, and is the faster one for long or large runs; with `backend_options={"standalone_directory": "brian2_build"}` (or `standalone_directory` in the simulation file's `backend.options`) it keeps its code in that folder and compiles only what changed since the last run there. Two runs at the same time must not share the folder. Its threads (`local_num_threads`) speed up the simulation itself; Brian2 creates the synapses on one thread.

Brian2 runs in one process (no MPI). Background input goes through static synapses only: each neuron gets a Poisson number of input spikes at each step, as from NEST's `poisson_generator`, and the input's delay is left out, since it only shifts a stationary Poisson train.

## Changing the core

Change the core when an idea doesn't fit what the config files can say (a new stimulus type, spatial structure, plasticity) and would help any model. If only one model needs it, it belongs in that model's builder. [CONTRIBUTING.md](../CONTRIBUTING.md#changing-the-core) shows which files each kind of change touches.

```text
microcircuit_lab/
├── config/            what each YAML file may contain (one module per file)
├── network/           reading, checking and preparing a network
├── simulation.py      Simulation: load, run, reopen a run
├── backends/          the simulators (NEST, Brian2), and reading back a saved run
├── analysis/          measures and plots
├── cli/               the microcircuit-lab command
├── builder_tools/     what a builder needs, in one import (also scaling)
├── run_folder.py      run folders and their metadata
├── project_code.py    finds the builders/, analyses/ and extensions/ of a project
└── yaml_files.py      reading and writing YAML
```

Only this folder is installed by `pip`. In a clone, `builders/`, `configs/`, `experiments/` and `extensions/` hold the examples, laid out like a project's.

### Adding a bundled plot

Like a project plot, with `register_plot` and a settings class, in `analysis/<plot>.py`. Also import the module in `analysis/__init__.py`, so it is registered when the package loads:

```python
register_plot("spectrogram", plot_spectrogram,
              config_cls=SpectrogramPlotConfig, filename="spectrogram.png")
```

## Adding a backend

1. Implement `SimulationBackend` (`microcircuit_lab/backends/interface.py`) in a package `microcircuit_lab/backends/<name>/`, like `nest/` or `brian2/`. `prepare_output` and `save_recordings` write the recordings in the simulator's own way; `get_spike_events` reads them back, so nothing else needs to know. `version()` gives the simulator's version for `metadata.json`.
2. Register it in `get_backend`, and its file reader (like `nest/spike_files.py`, which does not import the simulator) in `read_saved_spikes`, both in `microcircuit_lab/backends/__init__.py`. Saved runs can then be re-plotted without the simulator.
3. Add its name to `BackendName` (`microcircuit_lab/config/simulation.py`). Select it with `backend: {name: <name>, options: {...}}` in the simulation file, or `Simulation.from_yaml(..., backend="<name>", backend_options={...})`; the options go to its constructor unchanged.

## Testing

```bash
pytest
```

The tests cover the core: reading and checking configs, preparing a network, the simulator backends and the analysis. A builder is tested through what it writes: every network in `configs/network/` is loaded and checked. Tests that simulate need NEST; the Brian2 tests are skipped without Brian2.
