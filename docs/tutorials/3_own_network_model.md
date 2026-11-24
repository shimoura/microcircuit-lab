# 3 · Your own network model

Write a network model by hand: five short YAML files in a folder of their own. About ten minutes, in the project of [tutorial 1](1_first_run.md).

The model: 400 excitatory and 100 inhibitory neurons, each pair connected with probability 0.1, driven by Poisson input. Make its folder, and in it the five files below, in any editor:

```bash title="Terminal"
mkdir configs/network/my_model
```

## The files

`network.yaml` lists the other files:

```yaml title="configs/network/my_model/network.yaml"
populations: populations.yaml
neurons: neurons.yaml
connectivity: connectivity.yaml
poisson_background: poisson_background.yaml
```

`populations.yaml`: the populations, their sizes, and the neuron each one is made of ([Network files](../network-files.md) shows how the files name each other).

```yaml title="configs/network/my_model/populations.yaml"
populations:
  - name: E
    size: 400
    neuron: lif
  - name: I
    size: 100
    neuron: lif
```

`neurons.yaml`: the neuron, a NEST model with its parameters. Any NEST model works, with its own parameters.

```yaml title="configs/network/my_model/neurons.yaml"
neurons:
  lif:
    model: iaf_psc_exp
    parameters:
      C_m: 250.0        # pF
      tau_m: 10.0       # ms
      tau_syn_ex: 0.5   # ms
      tau_syn_in: 0.5   # ms
      E_L: -65.0        # mV
      V_reset: -65.0    # mV
      V_th: -50.0       # mV
      t_ref: 2.0        # ms
```

`connectivity.yaml`: one entry per pair of populations. The weight is the current each spike gives (pA): positive from E, negative and four times larger from I. The rules: [Connections](../connections.md); weights and delays, also drawn ones: [Weights and delays](../weights-and-delays.md).

```yaml title="configs/network/my_model/connectivity.yaml"
connections:
  - source: E
    target: E
    rule: pairwise_bernoulli
    p: 0.1
    weight: {value: 87.8, unit: pA}
    delay: {value: 1.5}
  - source: E
    target: I
    rule: pairwise_bernoulli
    p: 0.1
    weight: {value: 87.8, unit: pA}
    delay: {value: 1.5}
  - source: I
    target: E
    rule: pairwise_bernoulli
    p: 0.1
    weight: {value: -351.2, unit: pA}
    delay: {value: 0.8}
  - source: I
    target: I
    rule: pairwise_bernoulli
    p: 0.1
    weight: {value: -351.2, unit: pA}
    delay: {value: 0.8}
```

`poisson_background.yaml`: each neuron gets 1000 inputs, each firing 8 spikes/s.

```yaml title="configs/network/my_model/poisson_background.yaml"
poisson_background:
  E: {rate: 8.0, indegree: 1000, weight: {value: 87.8, unit: pA}, delay: {value: 1.5}}
  I: {rate: 8.0, indegree: 1000, weight: {value: 87.8, unit: pA}, delay: {value: 1.5}}
```

## Run it

With the toy's settings (1 s):

```bash title="Terminal"
microcircuit-lab run --network my_model --simulation toy
```

```text title="Output"
E       N=  400  spikes=   6935  rate=  17.337 Hz
I       N=  100  spikes=   1799  rate=  17.990 Hz
No analysis file at configs/analysis/my_model.yaml; using the default plot settings.
Run directory: output/my_model/20261120_205203
```

Without `--simulation`, the run looks for `configs/simulation/my_model.yaml`; without that file it uses the default settings (100 ms) and says so.

## A mistake

A mistake in a file stops the run before anything is simulated, and says which file and which field ([Checks](../network-files.md#checks)). Set a size to `0` and run again:

```text title="Output"
Invalid network config in configs/network/my_model:
  populations.yaml: populations.0.size: Input should be greater than 0
```

## More

- Every field of every file, with its unit and default: [Configuration files](../config_files.md).
- Weights given as PSPs, drawn values, other rules: [Weights and delays](../weights-and-delays.md), [Connections](../connections.md).
- When the numbers come from data, code can write these files for you: [Builders](../builders.md).

Next: [4 · A builder](4_builder.md).
