# The run folder

Every run gets a folder of its own, with everything it produced:

```text
output/<network>/<timestamp>/
├── recordings/          spikes (and recorded variables), written by the simulator
├── plots/               made by microcircuit-lab run
├── measures/            optional: analysis results kept for re-plotting (firing_rates.npz, ...)
├── final_connections/   optional: every synapse at the end of the run (below)
├── config.yaml          the network and the simulation settings used
└── metadata.json        versions (core, simulator, Python), git commits, MPI processes, run times, spike counts
```

`config.yaml` and `metadata.json` are enough to know, years later, what was simulated and with which code.

- Optional: `output.overwrite: true` in the simulation file reuses one folder instead, emptying what the run writes again.
- NEST writes the spikes straight to disk; Brian2 keeps them in memory and writes them at the end.

## Reading a run

`read_run` opens a run folder, without the simulator. The plots read runs this way, and so can your own analyses.

```python
from microcircuit_lab import read_run

run = read_run("output/toy/<timestamp>")
run.populations                  # ["E", "I"], in network order
spikes = run.spikes("E")         # spikes.senders, spikes.times (ms), sorted by sender
run.node_ids("E")                # the node IDs of the population
trace = run.recording("V_m")     # trace.senders, trace.times (ms), trace.values; needs recording.variables
run.reference                    # the reference rates, or None
run.network                      # the whole network as simulated (config.yaml), read when first used
run.simulation                   # the simulation settings (config.yaml), e.g. run.simulation.t_sim
run.metadata                     # metadata.json as a dict: simulator, seed, run times, spike counts
run.folder                       # the run folder, a pathlib.Path
```

The spike files are read once, at the first `run.spikes(...)`. A run made with an older version can still be plotted; only `run.network` may need that version, and says so.

Every function and attribute, with its arguments: [Python API](api.md#run-and-read).

## Recording other variables (optional)

Spikes are always recorded. Any neuron variable can be recorded too, named as the simulator names it, in the simulation file:

```yaml
recording:
  variables:
    V_m: {interval: 1.0, sample_size: 5}          # 5 neurons per population, every 1 ms
    I_syn_ex: {interval: 1.0, populations: [E]}   # synaptic input (g_ex for conductance-based models), all neurons of E
```

| Field | Meaning | Default |
| :--- | :--- | :--- |
| `interval` | ms between two samples | 1.0 |
| `sample_size` | the first N neurons of each population | all |
| `populations` | which populations | all |

- A name the model does not have fails in the simulator. Brian2 saves mV, ms, pA, nS and Hz; other dimensions in SI base units.
- `read_run(run_dir).recording("V_m")` returns `senders`, `times` (ms) and `values`, sorted by sender, then time.

## The synapses at the end of a run (optional)

After plasticity, for example, you may want the final weights. Ask for them in the simulation file, for every connection or some:

```yaml
recording:
  final_connections: true                       # or [{source: E, target: E}]
```

```text
final_connections/
├── connectivity.yaml          the rows as rule: from_file
└── synapses/E_to_E_stdp.csv   one file per row: <source>_to_<target>[_<synapse>].csv
```

Copied into a network folder, they run the network again with those weights and delays ([Connections from a file](connections.md#connections-from-a-file-optional)). Only weights and delays are saved; other synapse variables (STDP traces, the `u` and `x` of short-term plasticity) aren't saved yet, so they start from their initial values. It is off by default because it is slow (NEST takes about 4 µs per synapse: 3 min for pd14's largest projection, 45 M synapses), and it doesn't work with several MPI processes yet.

## From other tools

The run folder is plain files, so any language can read it:

| File | What it holds |
|---|---|
| `metadata.json` → `populations` | per population: `size`, `first_node_id`, `last_node_id` (one block of node IDs), `n_spikes` and `mean_rate_hz` over the whole run (the plots use the analysis window) |
| `metadata.json` → `build_time_s`, `simulate_time_s` | seconds spent building the network and simulating it |
| `recordings/spikes-*.dat` (NEST) | tab-separated `sender`, `time_ms`, after `#` comment lines; one file per thread |
| `recordings/spikes.csv` (Brian2) | `sender,time_ms` |
| `recordings/<variable>-*.dat` / `<variable>.csv` | `sender`, `time_ms`, the variable |
| `config.yaml` | the network and the simulation settings as run |

```python
import json
populations = json.load(open("output/toy/<timestamp>/metadata.json"))["populations"]
populations["E"]["first_node_id"], populations["E"]["last_node_id"]   # 1, 800
```
