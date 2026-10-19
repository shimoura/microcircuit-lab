# Config files

<!-- Written by docs/write_config_files.py from microcircuit_lab/config/; do not edit by hand. -->

Every field each config file accepts, as a YAML example. The comment above a field says whether it is required (or its default), the values it takes, and what it means. A mistake is reported when the network is read, naming the file and the field.

## A network: `configs/network/<name>/`

One folder per network, one file per part. A population is named once, in `populations.yaml`, and the other files use that name; a neuron likewise, in `neurons.yaml`. (`network.yaml` lists the files; `scaling.yaml` uses no names.)

![The files of a network refer to each other by name](images/config_names.svg)

What this means for a model:

- **A population has one neuron entry.** Every neuron in it gets the same model and the same parameters; only the starting membrane potential differs (drawn from `V0_mean` and `V0_std`).
- **Connections are set per pair of populations**: one entry for each source and target, with the number of synapses and the distributions their weights and delays are drawn from. Every connection uses the same rule (a fixed total number of synapses) and NEST's default synapse and receptor; several synapse models, receptors or rules for one pair (e.g. AMPA and NMDA) are not supported yet.
- **So, for neurons with another model or other parameters, or wired differently, make a separate population.** In `configs/network/toy_stimulated/`, `E` (`iaf_psc_exp`) and `E_adex` (`aeif_cond_exp`) are two populations, each with its own connections.
- **Several populations can share one neuron entry**, e.g. one `excitatory` entry for the excitatory populations of every layer.
- **Names are only labels.** `E` does not make a population excitatory: the sign of its outgoing weights does.

A small working example to copy: [`configs/network/toy/`](../configs/network/toy/).

### network.yaml

Names the file of each part. The names below are the usual ones.

```yaml
# required · text · file holding the populations list
populations: populations.yaml
# required · text · file holding the neuron definitions
neurons: neurons.yaml
# required · text · file holding the connection list
connectivity: connectivity.yaml
# required · text · file holding the background-input entries
background_inputs: background_inputs.yaml
# required · text · file holding the scaling parameters
scaling: scaling.yaml
# required · text · file holding the reference rates
reference: reference.yaml
# optional · text · file holding targeted stimuli; omit the key for none
stimuli: stimuli.yaml
```

### populations.yaml

The populations: size, neuron and initial state.

```yaml
# required · list of entries · one entry per population
populations:
  # required · text · unique population name; referenced by connectivity,
  #   background_inputs, stimuli and reference
  - name: L23_E
    # required · integer > 0 · number of neurons
    size: 20683
    # required · text · name of an entry in neurons.yaml; every neuron of the population
    #   gets that model and those parameters
    neuron: excitatory
    # required · number · mean initial membrane potential (mV)
    V0_mean: -58.0
    # required · number ≥ 0 · standard deviation of the initial potential (mV)
    V0_std: 10.0
    # optional, default 0.0 · number ≥ 0 · background-input connections per neuron;
    #   multiplies the rate in background_inputs.yaml
    background_indegree: 2510.0
```

### neurons.yaml

The neuron models, by name. Several populations can share one.

```yaml
# required · mapping · one entry per neuron, keyed by any name; populations refer to it
#   by that name
neurons:
  excitatory:
    # required · text · the simulator's neuron model name, e.g. iaf_psc_exp
    model: iaf_psc_exp
    # required · parameters passed to that model as-is; keys are model-specific and the
    #   backend validates them (I_e defaults to 0.0)
    parameters:
      C_m: 250.0
      tau_m: 10.0
      tau_syn_ex: 0.5
      tau_syn_in: 0.5
      E_L: -65.0
      V_th: -50.0
      V_reset: -65.0
      t_ref: 2.0
    # optional, default empty · mapping · only for `unit: PSP` connections whose neuron
    #   names C_m/tau_m/tau_syn_ex/tau_syn_in differently, e.g. {C_m: cm}
    psp_conversion_aliases: {}
```

### connectivity.yaml

The connections between populations.

```yaml
# required · list of entries · one entry per (source, target) pair; leave a pair out
#   rather than writing n_synapses: 0
connections:
  # required · text · source population name
  - source: L4_E
    # required · text · target population name
    target: L23_E
    # required · integer ≥ 0 · total number of synapses in the projection
    n_synapses: 1440000
    # required · weight of each synapse
    weight:
      # required · number · amplitude, in the unit set by `unit`; a negative weight is
      #   inhibitory
      mean: 0.15
      # required · number ≥ 0 · standard deviation / |mean|
      rel_std: 0.1
      # optional, default normal · one of normal | lognormal | fixed · how each weight
      #   is drawn
      distribution: normal
      # required · one of PSC | PSP | native · PSP: mV, converted to pA; PSC: pA, used
      #   as given; native: used as given (e.g. nS)
      unit: PSP
    # required · delay of each synapse
    delay:
      # required · number > 0 · mean delay (ms)
      mean: 1.5
      # required · number ≥ 0 · standard deviation / mean
      rel_std: 0.5
      # optional, default normal · one of normal | lognormal | fixed · how each delay is
      #   drawn
      distribution: normal
      # optional · number > 0 · smallest allowed delay (ms) of a drawn delay, never
      #   below half the simulation step; omit for half the simulation step
      minimum: 0.1
# optional, default redraw · one of redraw | clip · what to do with a drawn weight or
#   delay outside its allowed range: 'redraw' draws again, 'clip' replaces it by the
#   limit; applies to all weights and delays of the network, background inputs included
bound_mode: redraw
```

### background_inputs.yaml

The always-on Poisson input of each population.

```yaml
# required · mapping · one entry per population, keyed by its name; a population left
#   out gets none
background_inputs:
  L23_E:
    # required · number ≥ 0 · background Poisson rate per connection (spikes/s)
    rate: 8.0
    # required · weight of each background connection
    weight: {mean: 0.15, rel_std: 0.1, unit: PSP}   # all fields as in connectivity.yaml
    # required · delay of each background connection
    delay: {mean: 1.5, rel_std: 0.5}   # all fields as in connectivity.yaml
# optional, default poisson · one of poisson | dc · 'dc' replaces the Poisson drive
#   network-wide with a constant current of the same mean
background_mode: poisson
```

### stimuli.yaml

Optional: inputs for an experiment, applied as written (never scaled).

```yaml
# optional, default empty · list of entries · one entry per stimulus; `type` selects its
#   fields
stimuli:
  # Constant-current pulse. Current is injected directly; no weight/delay.
  # required · selects the fields below
  - type: dc
    # required · list of names, at least 1 · population names to stimulate; one device,
    #   connected to every neuron of each
    targets: [L4_E, L4_I]
    # optional, default 0.0 · number ≥ 0 · when the stimulus starts (ms)
    start: 0.0
    # optional · number > 0 · when it stops (ms); omit to keep it on until the end
    stop: 600.0
    # required · number · current (pA)
    amplitude: 200.0
  # Homogeneous Poisson spike train, active for [start, stop).
  # required · selects the fields below
  - type: poisson
    # required · list of names, at least 1 · population names to stimulate; one device,
    #   connected to every neuron of each
    targets: [L4_E, L4_I]
    # optional, default 0.0 · number ≥ 0 · when the stimulus starts (ms)
    start: 0.0
    # optional · number > 0 · when it stops (ms); omit to keep it on until the end
    stop: 600.0
    # required · number ≥ 0 · spike rate (spikes/s)
    rate: 50.0
    # required · weight of each stimulus connection
    weight: {mean: 0.15, rel_std: 0.1, unit: PSP}   # all fields as in connectivity.yaml
    # required · delay of each stimulus connection
    delay: {mean: 1.5, rel_std: 0.5}   # all fields as in connectivity.yaml
  # Poisson spike train with a piecewise-constant rate profile.
  # required · selects the fields below
  - type: inhomogeneous_poisson
    # required · list of names, at least 1 · population names to stimulate; one device,
    #   connected to every neuron of each
    targets: [L4_E, L4_I]
    # optional, default 0.0 · number ≥ 0 · when the stimulus starts (ms)
    start: 0.0
    # optional · number > 0 · when it stops (ms); omit to keep it on until the end
    stop: 600.0
    # required · list of numbers, at least 1 · when the rate changes (ms), increasing
    rate_times: [200.0, 400.0]
    # required · list of numbers, at least 1 · the rate from each of those times on
    #   (spikes/s), one per time
    rate_values: [20.0, 0.0]
    # required · weight of each stimulus connection
    weight: {mean: 0.15, rel_std: 0.1, unit: PSP}   # all fields as in connectivity.yaml
    # required · delay of each stimulus connection
    delay: {mean: 1.5, rel_std: 0.5}   # all fields as in connectivity.yaml
```

### scaling.yaml

How to downscale the network; see "Scaling a network" in the README.

```yaml
# optional, default 1.0 · number > 0 · multiplies the number of neurons
N_scaling: 1.0
# optional, default 1.0 · number > 0 · multiplies the indegrees (synapses per neuron)
K_scaling: 1.0
# optional, default true · true or false · add a DC current that restores the mean input
#   lost by scaling
preserve_mean_input: true
# optional, default true · true or false · true: weights / sqrt(K_scaling), keeps the
#   fluctuations; false: weights / K_scaling, keeps the mean and needs no DC current
preserve_variance: true
# optional, default true · true or false · the DC current also replaces the lost
#   recurrent input (needs reference.full_mean_rates); false: only the lost background
#   input
compensate_recurrent_input: true
```

### reference.yaml

Published values to compare with, and to compensate a scaled network.

```yaml
# optional, default empty · mapping · mean rate (spikes/s) of each population at full
#   scale; needed when a scaled network compensates the recurrent input, and shown next
#   to the rates of a run
full_mean_rates:
  L23_E: 0.97
  L23_I: 2.9
```

## Running it: `configs/simulation/`

`microcircuit-lab run --network <name>` uses `configs/simulation/<name>.yaml`, or the defaults below when there is none.

### simulation/<name>.yaml

How to run: duration, seed, threads, what to record and save.

```yaml
# optional, default 100.0 · number > 0 · simulated time (ms)
t_sim: 100.0
# optional, default 0.1 · number > 0 · simulation time step (ms)
resolution: 0.1
# optional, default 42 · integer · seed of the random numbers
rng_seed: 42
# optional, default 1 · integer ≥ 1 · threads per process
local_num_threads: 1
# optional, default true · true or false · print the simulation progress
print_time: true
# optional · what to record
recording:
  # optional, default true · true or false · record the spikes of every neuron
  spike_recording: true
  # optional, default false · true or false · record membrane potentials
  voltage_recording: false
  # optional, default 1.0 · number > 0 · time between two voltage samples (ms)
  voltage_interval: 1.0
  # optional, default 5 · integer ≥ 1 · neurons per population whose voltage is
  #   recorded; null records all
  voltage_sample_size: 5
# optional · where and what to save
output:
  # optional · path · folder for the runs; omit for output/<network name>
  output_dir: output/pd14
  # optional, default false · true or false · false: each run gets its own
  #   <output_dir>/<date_time> folder; true: every run writes into output_dir itself
  overwrite: false
  # optional, default true · true or false · write metadata.json (versions, spike
  #   counts, files written); needed with config.yaml to re-plot the run
  save_metadata: true
  # optional, default true · true or false · write config.yaml (the prepared network);
  #   needed to re-plot the run
  save_config: true
```
