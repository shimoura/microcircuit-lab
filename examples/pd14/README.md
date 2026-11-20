# PD14 example

The cortical microcircuit of Potjans & Diesmann (2014): 77,169 neurons in four layers, an excitatory and an inhibitory population in each, about 300 million synapses. Everything specific to PD14 stays here; the core runs the result like any other network.

## Run it

From this folder (`cd examples/pd14` in the repository), or from a project that has the example (`microcircuit-lab init <project> --example pd14`):

```bash title="Terminal"
microcircuit-lab run --network pd14_downscaled   # 10 % of the neurons: runs on a laptop
microcircuit-lab run --network pd14              # the full model: about 15 GB of memory
```

| Network | What it is |
| :--- | :--- |
| `pd14` | the full model |
| `pd14_downscaled` | N and K scaled by 0.1, with the compensation current ([Scaling a network model](../../docs/scaling.md)). Most rates are within 10–20 % of the full model; L2/3 E is lower (0.5 instead of 0.9 spikes/s) |

## Write the networks again (optional)

The bundled network folders were written by the builder. Write them again after changing `data.py`:

```bash title="Terminal"
microcircuit-lab generate pd14
microcircuit-lab generate pd14 --n-scaling 0.1 --k-scaling 0.1 --network-name pd14_downscaled
```

The paper's Fig. 5 replaces the Poisson background by a constant current of the same mean (after scaling, before writing):

```bash title="Terminal"
microcircuit-lab generate pd14 --network-name pd14_mean_current --background mean_current
microcircuit-lab run --network pd14_mean_current --simulation pd14 --analysis pd14

# the same at 10 %
microcircuit-lab generate pd14 --n-scaling 0.1 --k-scaling 0.1 --background mean_current \
    --network-name pd14_downscaled_mean_current
microcircuit-lab run --network pd14_downscaled_mean_current --simulation pd14_downscaled --analysis pd14
```

## The builder (`builders/pd14/`)

- `data.py`: the PD14 parameters, each with its source.
- `build.py`: writes `configs/network/pd14/` from `data.py`. Connection probabilities become synapse numbers (`num_synapses_from_conn_prob`), and PSPs (mV) the currents (pA) that give them (`psp_to_psc_iaf_psc_exp`), both from `microcircuit_lab.builder_tools`. `main(argv)` is what `microcircuit-lab generate pd14` calls.

## Sources

- Potjans, T. C., & Diesmann, M. (2014). The cell-type specific cortical microcircuit: relating structure and activity in a full-scale spiking network model. *Cerebral Cortex*, 24(3), 785–806. https://doi.org/10.1093/cercor/bhs358
- The official PyNEST implementation, [INM-6/microcircuit-PD14-model](https://github.com/INM-6/microcircuit-PD14-model), commit `f79f8ac`, `network_params.py`. The optimized initial membrane potentials and the reference rates come from this implementation only.
