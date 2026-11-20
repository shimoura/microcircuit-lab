# Jiang et al. (2024) example

The layered microcircuit of mouse somatosensory cortex of Jiang et al. (2024), with PV, SOM and VIP interneurons and without thalamic input: 13 populations, 6,448 neurons. Everything specific to this model stays here; the core runs the result like any other network.

| Network | What it is |
| :--- | :--- |
| `jiang24` | the paper's Base model, with static synapses |
| `jiang24_stp` | the paper's Base-STP model: cell-type-specific short-term plasticity (STP) on most projections, the weights of those projections scaled up, and background rates of its own. On NEST for now (below) |

## Run it

From this folder (`cd examples/jiang24` in the repository), or from a project that has the example (`microcircuit-lab init <project> --example jiang24`):

```bash title="Terminal"
microcircuit-lab run --network jiang24
microcircuit-lab run --network jiang24_stp
```

- The simulation files have the paper's 15 s at a 0.1 ms time step, on 16 threads. The delays depend on the time step (below).
- The paper leaves out the first 10 s when it analyses these runs; the default plots cover the whole run.
- The STP synapses are NEST's `tsodyks_synapse`. The example has no Brian2 version of it yet (its `tsodyks2_synapse` is a different model), so `jiang24_stp` runs on NEST for now.

## The plots of Fig. 6 (optional)

Two plots have the form of the paper's Fig. 6 (A: Base, B: Base-STP), to compare the two models: `jiang24_raster.png` and `jiang24_firing_rates.png`. They live in `analyses/` (`init --example jiang24` copies them), as an example of plots of your own outside the core ([Analysing a run](../../docs/analysis.md)). They are off by default; the analysis files `jiang24_fig6` and `jiang24_stp_fig6` switch them on, with the paper's time windows and experimental rates:

```bash title="Terminal"
microcircuit-lab run --network jiang24 --analysis jiang24_fig6
microcircuit-lab run --network jiang24_stp --analysis jiang24_stp_fig6
microcircuit-lab run --run-dir output/jiang24/<timestamp> --analysis jiang24_fig6   # a finished run, without simulating again
```

The paper's firing-rate panel pools the neurons of 20 simulations; the plot above shows one run. For the pooled panel:

```bash title="Terminal"
python experiments/jiang24/run_seeds.py      # the paper's 20 seeds, in output/jiang24_seeds/
python analyses/jiang24_firing_rates.py output/jiang24_seeds/firing_rates.png output/jiang24_seeds/seed_*/*

python experiments/jiang24_stp/run_seeds.py  # the same for jiang24_stp, in output/jiang24_stp_seeds/
python analyses/jiang24_firing_rates.py output/jiang24_stp_seeds/firing_rates.png output/jiang24_stp_seeds/seed_*/*
```

Both take their plot settings from `jiang24_fig6`, which are the same for the two models.

## Write the networks again (optional)

The bundled network, simulation and analysis files were written by the builder. Write them again after changing `data.py`:

```bash title="Terminal"
microcircuit-lab generate jiang24          # configs/network/jiang24/, and jiang24*.yaml in configs/simulation/ and configs/analysis/
microcircuit-lab generate jiang24 --stp    # the same for jiang24_stp
```

## What follows the official code

- **Neurons:** `iaf_psc_exp`, with parameters per cell type, shared by L2/3 and L4 and by L5 and L6 (Table 2).
- **Connections:** `pairwise_bernoulli` with the probability of each projection (Fig. 3); autapses allowed.
- **Weights:** lognormal, keeping their sign, with a standard deviation equal to the mean. PSPs are 0.5 mV (excitatory) and −2 mV (inhibitory), written as the currents (pA) that give them with each target's neuron.
- **Delays:** lognormal, 1.36 ± 0.51 ms (excitatory) and 1.43 ± 1.09 ms (inhibitory); values below 0.1 ms, the time step, are drawn again.
- **Background:** each neuron gets one Poisson train, with a rate per cell type (E 5000, PV 6900, SOM 2500, VIP 3300 spikes/s), a fixed PSP of 0.5 mV, a delay of 0.1 ms and a static synapse. The file writes this as `indegree: 1`, with `rate` the rate of the train. The official code goes through one parrot neuron per target, which gives each neuron the same independent train.
- **Initial state:** `V_m` normal, −62 ± 5 mV, from the code only.

With `--stp`, three things change:

- **Short-term plasticity:** NEST's `tsodyks_synapse`, with U, `tau_fac` and `tau_rec` per projection (Fig. 5B): 20 entries of `synapses.yaml`, named `stp_<source>_to_<target>`.
  - Projections between E, PV and SOM cells have one set per pair of cell types, for every layer; those between E cells have one per pair of layers (the pairs without one have probability 0).
  - Projections from and onto VIP cells, and SOM→SOM, stay static.
  - Each synapse's `tau_psc` is the time constant of its source's input (2 ms excitatory, 4 ms inhibitory). The synapses start from NEST's default state, as in the code.
- **Weights:** the mean PSP of each projection with STP is multiplied by a factor (Fig. 5C, from 1.05 to 8.8), which makes the synapse settle at the static PSC when its source fires regularly at that population's rate in a static simulation. The code fits these factors in each simulation, from a static run with the same seed and this model's background rates, so they change with the seed (by up to 10 %). `data.py` has their means over the paper's 20 simulations, the values of Fig. 5C.
- **Background:** the rates fitted for this model, E 5000, PV 6800, SOM 2400, VIP 3600 spikes/s.

`reference.yaml` has the mean rates of each model over 20 simulations of the official code (Table 5 gives them rounded).

## Where the code and the paper differ

The builder follows the official code, which made the published results:

- **SOM connections in L5:** the Methods say L5 Exc→SOM, SOM→Exc and SOM→SOM are averages of L2/3 and L4. The code's `Helper.hybrid_conn` averages L5 SOM→PV, PV→SOM and SOM→SOM instead, and the values in Fig. 3 agree with the code.
- **Unused values:** the code's `model/net_dict.json` holds other background rates (`K_ext`) and scaled PSPs (`psp_means`, `w_mod_custom`). The code replaces them when it builds the network, so neither model uses them. The input columns saved with the published runs (`results_pop.csv` of `snake_gs-static` and `snake_gs-stp` in `snakes_main.zip`) match the values here.

## The builder (`builders/jiang24/`)

- `data.py`: the parameters, each with its source; those of the Base-STP model alone are in the section at the end.
- `build.py`: writes `configs/network/jiang24/` (or `jiang24_stp/` with `--stp`) and the simulation and analysis files, from `data.py`. `main(argv)` is what `microcircuit-lab generate jiang24` calls.

## Sources

- Jiang, H.-J., Qi, G., Duarte, R., Feldmeyer, D., & van Albada, S. J. (2024). A layered microcircuit model of somatosensory cortex with three interneuron types and cell-type-specific short-term plasticity. *Cerebral Cortex*, 34(9), bhae378. https://doi.org/10.1093/cercor/bhae378
- The official code, https://zenodo.org/doi/10.5281/zenodo.10069507. Where the paper rounds a value, `data.py` has the one the code uses.
