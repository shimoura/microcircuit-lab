# Jiang et al. (2024) builder

Writes the network files of the layered microcircuit model of mouse somatosensory cortex of Jiang et al. (2024), with PV, SOM and VIP interneurons. This is the version with static synapses, the publication's Base model: 13 populations and 6,448 neurons. Everything specific to this model stays here; the core runs the result like any other network.

## Sources

- Jiang, H.-J., Qi, G., Duarte, R., Feldmeyer, D., & van Albada, S. J. (2024). A layered microcircuit model of somatosensory cortex with three interneuron types and cell-type-specific short-term plasticity. *Cerebral Cortex*, 34(9), bhae378. https://doi.org/10.1093/cercor/bhae378
- The official code, https://zenodo.org/doi/10.5281/zenodo.10069507. Where the publication rounds a value, `data.py` has the one the code uses.

## Generate and run

```bash
microcircuit-lab generate jiang24     # writes configs/network/jiang24/ and jiang24.yaml in configs/simulation/ and configs/analysis/
microcircuit-lab run --network jiang24
```

The simulation file has the publication's 15 s at a 0.1 ms time step, on which the delays depend (below). The publication leaves out the first 10 s when it analyses this run. Besides the bundled plots, which cover the whole run, the analysis file switches on `jiang24_raster.png`, the raster plot with the axes of Fig. 6A (`analyses/jiang24_raster.py`).

## What follows the official code

- **Neurons:** `iaf_psc_exp`, with parameters per cell type, shared by L2/3 and L4 and by L5 and L6 (Table 2).
- **Connections:** `pairwise_bernoulli` with the probability of each projection (Fig. 3); autapses allowed.
- **Weights:** lognormal, keeping their sign, with a standard deviation equal to the mean. PSPs are 0.5 mV (excitatory) and −2 mV (inhibitory), written as the currents (pA) that give them with each target's neuron.
- **Delays:** lognormal, 1.36 ± 0.51 ms (excitatory) and 1.43 ± 1.09 ms (inhibitory); values below 0.1 ms, the time step, are drawn again.
- **Background:** each neuron gets one Poisson train, with a rate per cell type (E 5000, PV 6900, SOM 2500, VIP 3300 spikes/s), a fixed PSP of 0.5 mV and a delay of 0.1 ms. The file writes this as `indegree: 1` with `rate` the rate of the train. The official code goes through one parrot neuron per target, which gives each neuron the same independent train.
- **Initial state:** `V_m` normal, −62 ± 5 mV, from the code only.

`reference.yaml` has the mean rates of the Base model over 20 simulations of the official code (Table 5 gives them rounded).

## Where the code and the publication differ

The numbers follow the code, which made the published results:

- The Methods say L5 Exc→SOM, SOM→Exc and SOM→SOM are averages of L2/3 and L4. `Helper.hybrid_conn` averages L5 SOM→PV, PV→SOM and SOM→SOM instead, and the values in Fig. 3 agree with the code.
- `model/net_dict.json` holds other background rates (`K_ext`), scaled PSPs (`psp_means`, `w_mod_custom`) and 0.3115 instead of 0.3114 for L5 and L6 PV→SOM (`conn_probs`). The code replaces them when it builds the network, so the Base model does not use them; the input columns saved with the published runs (`results_pop.csv` in `snakes_main.zip`) match the values here.

## Not included yet

Short-term plasticity (Base-STP), the thalamic input, the cell-type-specific stimulation, and the TC-adjusted and double-sized versions.

## Files

- `data.py`: the parameters, each with its source.
- `build.py`: writes `configs/network/jiang24/` and the simulation and analysis files from `data.py`. `main(argv)` is the entry point `microcircuit-lab generate jiang24` calls.
