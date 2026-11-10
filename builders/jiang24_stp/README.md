# Jiang et al. (2024) builder, with short-term plasticity

Writes the network files of the layered microcircuit model of mouse somatosensory cortex of Jiang et al. (2024), with PV, SOM and VIP interneurons. This is the version with cell-type-specific short-term plasticity (STP) and without thalamic input, the publication's Base-STP model: 13 populations and 6,448 neurons. It is the Base model of [`builders/jiang24`](../jiang24/README.md) with STP on most projections, the weights of those projections scaled up, and its own background rates. Everything specific to this model stays here; the core runs the result like any other network.

## Sources

- Jiang, H.-J., Qi, G., Duarte, R., Feldmeyer, D., & van Albada, S. J. (2024). A layered microcircuit model of somatosensory cortex with three interneuron types and cell-type-specific short-term plasticity. *Cerebral Cortex*, 34(9), bhae378. https://doi.org/10.1093/cercor/bhae378
- The official code, https://zenodo.org/doi/10.5281/zenodo.10069507. Where the publication rounds a value, `data.py` has the one the code uses.

## Generate and run

```bash
microcircuit-lab generate jiang24_stp     # writes configs/network/jiang24_stp/, jiang24_stp.yaml in configs/simulation/ and configs/analysis/, and jiang24_stp_fig6.yaml in configs/analysis/
microcircuit-lab run --network jiang24_stp
```

The simulation file has the publication's 15 s at a 0.1 ms time step, on which the delays depend (below). The publication leaves out the first 10 s when it analyses this run; the bundled plots cover the whole run.

The synapses with STP are NEST's `tsodyks_synapse`, so this network runs on NEST only: `extensions/brian2/` does not have that model (its `tsodyks2_synapse` is a different one).

## The plots of Fig. 6B

The two plots of [jiang24](../jiang24/README.md#the-plots-of-fig-6a), `jiang24_raster.png` and `jiang24_firing_rates.png` (`analyses/jiang24_*.py`), have the form of Fig. 6B of the original paper, the panel of this model. The analysis file `jiang24_stp_fig6` switches them on, with the same time windows and experimental rates as `jiang24_fig6`:

```bash
microcircuit-lab run --network jiang24_stp --analysis jiang24_stp_fig6
microcircuit-lab run --run-dir output/jiang24_stp/<timestamp> --analysis jiang24_stp_fig6     # a finished run, without simulating it again
```

`microcircuit-lab init --with-core` copies this builder and the configs, but not `analyses/` or `experiments/`. In such a project, first copy `analyses/jiang24_raster.py` and `analyses/jiang24_firing_rates.py` from this repository, or `jiang24_stp_fig6` stops with an error about unknown plot sections, after any simulation.

The publication's firing rate panel pools the neurons of 20 simulations, while this plot shows one run. For the pooled panel (in a project, copy `experiments/jiang24_stp/run_seeds.py` too; the plot takes its settings from `jiang24_fig6`, which are the same):

```bash
python experiments/jiang24_stp/run_seeds.py     # the publication's 20 seeds, in output/jiang24_stp_seeds/
python analyses/jiang24_firing_rates.py output/jiang24_stp_seeds/firing_rates.png output/jiang24_stp_seeds/seed_*/*
```

## What follows the official code

- **Neurons:** `iaf_psc_exp`, with parameters per cell type, shared by L2/3 and L4 and by L5 and L6 (Table 2).
- **Connections:** `pairwise_bernoulli` with the probability of each projection (Fig. 3); autapses allowed.
- **Short-term plasticity:** NEST's `tsodyks_synapse`, with U, `tau_fac` and `tau_rec` per projection (Fig. 5B): 20 entries of `synapses.yaml`, named `stp_<source>_to_<target>`. Projections between E, PV and SOM cells have one set per pair of cell types, for every layer; those between E cells have one per pair of layers (the pairs without one have probability 0). Projections from and onto VIP cells, and SOM→SOM, stay static. Each synapse's `tau_psc` is the time constant of its source's input (2 ms excitatory, 4 ms inhibitory). The synapses start from NEST's default state, as in the code.
- **Weights:** lognormal, keeping their sign, with a standard deviation equal to the mean. PSPs are 0.5 mV (excitatory) and −2 mV (inhibitory), written as the currents (pA) that give them with each target's neuron. With STP, the mean PSP is multiplied by a factor (Fig. 5C, from 1.05 to 8.8), so that the synapse settles at the static PSC when its source fires regularly at that population's rate in a static simulation. The code fits these factors in each simulation, from a static run with the same seed and this model's background rates, so they change with the seed (by up to 5 %); `data.py` has their means over the publication's 20 simulations, the values of Fig. 5C.
- **Delays:** lognormal, 1.36 ± 0.51 ms (excitatory) and 1.43 ± 1.09 ms (inhibitory); values below 0.1 ms, the time step, are drawn again.
- **Background:** each neuron gets one Poisson train, with a rate per cell type fitted for this model (E 5000, PV 6800, SOM 2400, VIP 3600 spikes/s; the Base model has PV 6900, SOM 2500, VIP 3300), a fixed PSP of 0.5 mV, a delay of 0.1 ms and a static synapse. The file writes this as `indegree: 1` with `rate` the rate of the train. The official code goes through one parrot neuron per target, which gives each neuron the same independent train.
- **Initial state:** `V_m` normal, −62 ± 5 mV, from the code only.

`reference.yaml` has the mean rates of the Base-STP model over 20 simulations of the official code (Table 5 gives them rounded).

## Where the code and the publication differ

The current implementation follows the original code, which made the published results. The connection probabilities and `model/net_dict.json` differ from the publication as for the Base model ([jiang24](../jiang24/README.md#where-the-code-and-the-publication-differ)); the input columns saved with the published runs (`snake_gs-stp/results_pop.csv` in `snakes_main.zip`) match the background rates here.

## Files

- `data.py`: the parameters, each with its source.
- `build.py`: writes `configs/network/jiang24_stp/` and the simulation and analysis files from `data.py`. `main(argv)` is the entry point `microcircuit-lab generate jiang24_stp` calls.
