# HuMAM example

The human multi-area model (HuMAM, Pronold et al. 2024), written from its data: one area, or all 34. Everything specific to HuMAM stays here; the core runs the result like any other network.

## Run it

From this folder (`cd examples/humam` in the repository), or from a project that has the example (`microcircuit-lab init <project> --example humam`):

```bash title="Terminal"
microcircuit-lab run --network humam_single   # one area, 56 neurons
microcircuit-lab run --network humam_all      # all 34 areas, 13,874 neurons, 16 threads
```

| Network | What it is |
| :--- | :--- |
| `humam_single` | the area `rostralanteriorcingulate`, at 0.1 % of its neurons and synapses |
| `humam_all` | all 34 areas at 0.4 %, simulated for 2 s |

Both are scaled far down: their files hold the numbers that are simulated, with the compensation current in `I_e`, and `scaling.yaml` records how they were made. The recurrent and background input that scaling removes is replaced by a constant current, computed from the full-scale rates in `reference.yaml` (mean-field estimates). So the network keeps its mean rates near those estimates, but not its fluctuations or correlations: a quick check, not the model's result.

## Write the networks again (optional)

These commands write the bundled network and simulation files:

```bash title="Terminal"
microcircuit-lab generate humam                    # humam_single
microcircuit-lab generate humam --area all --n-scaling 0.004 --k-scaling 0.004 --t-sim 2000 --threads 16   # humam_all
```

- `--area <name>` picks another area (the names are in `data/net.yaml`, `area_list`).
- A single area gets a constant current in place of the input from the areas it is cut off from; `--no-compensate-missing-areas` leaves it out.
- `--n-scaling` and `--k-scaling` are 0.001 by default.
- `microcircuit-lab generate humam --help` lists every option.

From Python:

```python
from builders.humam import generate_humam_configs
from microcircuit_lab import Simulation

generate_humam_configs(area="rostralanteriorcingulate", config_dir="configs",
                       network_name="humam_single", simulation_name="humam_single")
Simulation.from_yaml(network_name="humam_single", simulation_name="humam_single").run()
```

## What follows the HuMAM code

The builder builds the network as HuMAM `main` does (`src/simulation.py`, `src/default_sim_params.py`):

- weights in pA (`unit: pA`), as in the bundled data; normal, and clipped at 0 keeping their sign (`lower_bound: 0` or `upper_bound: 0`, `bound_mode: clip`);
- delays lognormal, from `delay_distribution` in `data/net.yaml`, clipped at the resolution (`lower_bound: 0.1`, `bound_mode: clip`), within and between areas;
- the background input with a fixed delay of the resolution;
- initial membrane potentials from a normal distribution with mean −150 mV and SD 50 mV;
- neuron parameters from `neuron_params_<type>` in `data/net.yaml`, one entry per population type; a local connection gets the excitatory or inhibitory delay by the sign of its weight, so no population name is assumed;
- no connections with a weight of 0.

## The builder (`builders/humam/`)

- `build.py`: turns the HuMAM data into network and simulation files, and checks them with `read_network` at the end. Its `main(argv)`, re-exported from `__init__.py`, is what `microcircuit-lab generate humam` calls.
- `data/`: network data produced by the HuMAM code at full scale (neuron and synapse numbers, weights, delays, external input, theoretical rates), with cortico-cortical scaling 1.0 (E→E) and 2.0 (E→I). The parameters used are in `data/network_params.yaml`.

Anything new and specific to HuMAM goes here, not in the core.

## Sources

- Pronold, J., van Meegen, A., Shimoura, R. O., Vollenbröker, H., Senden, M., Hilgetag, C. C., Bakker, R., & van Albada, S. J. (2024). Multi-scale spiking network model of human cerebral cortex. *Cerebral Cortex*. https://doi.org/10.1093/cercor/bhae409
- The HuMAM code, [INM-6/human-multi-area-model](https://github.com/INM-6/human-multi-area-model), `main` at commit `cab39b3`.
