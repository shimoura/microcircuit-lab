# Toy example

Two populations, 800 excitatory and 200 inhibitory neurons (`iaf_psc_exp`) with sparse random connections and a Poisson background, in the spirit of Brunel (2000). It is the smallest example, the one `microcircuit-lab init` puts in every project, and the one the tests run from.

## Run it

From this folder (`cd examples/toy` in the repository), or from any project (`microcircuit-lab init <project>` copies the toy):

```bash title="Terminal"
microcircuit-lab run --network toy                # about 20 spikes/s in both populations
microcircuit-lab generate toy                     # the builder writes configs/network/toy_from_builder/
microcircuit-lab run --network toy_from_builder --simulation toy --analysis toy
microcircuit-lab run --network toy_stimulated     # with constant-current and Poisson pulses
```

## Networks

| Network | What it shows |
| :--- | :--- |
| `toy` | written by hand: every file has comments that explain its fields, and each weight its PSP |
| `toy_from_builder` | the same network, written by `builders/toy/`; it gives the same spikes as `toy` |
| `toy_stimulated` | the toy network next to a copy made of `aeif_cond_exp` neurons, with `dc` and `poisson` stimuli in `stimuli.yaml` |

## Files

- `builders/toy/build.py`: the builder, short enough to read in one go. `microcircuit-lab generate toy` calls its `main(argv)`.
- `experiments/toy/background_drive_sweep.py`: a parameter sweep over the background indegree; [Tutorial 5](../../docs/tutorials/5_parameter_sweep.ipynb) walks through the same script.
- `extensions/brian2/`: the Brian2 versions of the NEST models the networks use (`iaf_psc_exp`, `aeif_cond_exp`), and NEST's `exponential` distribution.
