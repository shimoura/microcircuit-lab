# PD14 builder

Writes the network files of the Potjans & Diesmann (2014) cortical microcircuit. Everything specific to PD14 stays here; the core runs the result like any other network.

## Sources

- Potjans, T. C., & Diesmann, M. (2014). The cell-type specific cortical microcircuit: relating structure and activity in a full-scale spiking network model. *Cerebral Cortex*, 24(3), 785–806. https://doi.org/10.1093/cercor/bhs358
- The official PyNEST implementation, [INM-6/microcircuit-PD14-model](https://github.com/INM-6/microcircuit-PD14-model), commit `f79f8ac`, `network_params.py`. The optimized initial membrane potentials and the reference rates come from this implementation only.

## Generate and run

The bundled `configs/network/pd14/` was written by this builder. Write it again after changing `data.py`:

```bash
microcircuit-lab generate pd14
microcircuit-lab run --network pd14
```

For the publication's Fig. 5, which replaces the Poisson background by a constant current of the same mean (a step after scaling, before writing), write a second network:

```bash
microcircuit-lab generate pd14 --network-name pd14_mean_current --background mean_current
microcircuit-lab run --network pd14_mean_current --simulation pd14 --analysis pd14

# quick check: scaled by 0.1, then the background replaced
microcircuit-lab generate pd14 --n-scaling 0.1 --k-scaling 0.1 --background mean_current \
    --network-name pd14_downscaled_mean_current
microcircuit-lab run --network pd14_downscaled_mean_current --simulation pd14_downscaled --analysis pd14
```

The full network has 77,169 neurons and about 300 million synapses; building it needs about 15 GB of memory. For a quick check, run `configs/network/pd14_downscaled/` (N and K scaled by 0.1), made by

```bash
microcircuit-lab generate pd14 --n-scaling 0.1 --k-scaling 0.1 --network-name pd14_downscaled
microcircuit-lab run --network pd14_downscaled --analysis pd14
```

(see "Scaling a network" in `microcircuit_lab/README.md`).

## Files

- `data.py`: the PD14 parameters, each with its source.
- `build.py`: writes `configs/network/pd14/` from `data.py`; connection probabilities become synapse numbers with `num_synapses_from_conn_prob`, and the PSPs (mV) the currents (pA) that give them with `psp_to_psc_iaf_psc_exp`, both from `microcircuit_lab.builder_tools`. `main(argv)` is the entry point `microcircuit-lab generate pd14` calls.
