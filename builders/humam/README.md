# HuMAM model integration

This package translates HuMAM source data into Microcircuit Lab's generic network configuration format. HuMAM-specific data handling stays here; simulation is handled by the generic core and selected backend.

## Sources

- Pronold, J., van Meegen, A., Shimoura, R. O., Vollenbröker, H., Senden, M., Hilgetag, C. C., Bakker, R., & van Albada, S. J. (2024). Multi-scale spiking network model of human cerebral cortex. *Cerebral Cortex*. https://doi.org/10.1093/cercor/bhae409
- The HuMAM code, [INM-6/human-multi-area-model](https://github.com/INM-6/human-multi-area-model), `main` at commit `cab39b3`.

`data/` holds network data produced by the HuMAM code at full scale (neuron and synapse numbers, weights, delays, external input, theoretical rates), with cortico-cortical scaling 1.0 (E→E) and 2.0 (E→I); the parameters it was produced with are in `data/network_params.yaml`.

## Generate and run

From the repository root, these commands reproduce the bundled configs:

```bash
microcircuit-lab generate humam                    # humam_single: area rostralanteriorcingulate, 0.1 % of the neurons
microcircuit-lab generate humam --area all --n-scaling 0.004 --k-scaling 0.004 --t-sim 2000 --threads 16   # humam_all
```

`--area <name>` picks another area (names from `data/net.yaml`, `area_list`). A single area gets a constant current in place of the input from the areas it is cut off from (`--no-compensate-missing-areas` turns it off).

The command generates configurations under `configs/network/` and `configs/simulation/`.

Generation only writes portable configuration files. Run them separately with `microcircuit-lab run`. Use `microcircuit-lab generate humam --help` for the available generation options.

## What follows HuMAM

The builder reproduces how HuMAM `main` ([INM-6/human-multi-area-model](https://github.com/INM-6/human-multi-area-model), commit `cab39b3`, `src/simulation.py`, `src/default_sim_params.py`) builds the network:

- weights are written in pA (`unit: PSC`), as in the bundled data; normal, and clipped at 0 keeping their sign (`bound_mode: clip`);
- delays follow `delay_distribution` in `data/net.yaml` (lognormal), clipped at a minimum of the resolution (0.1 ms), locally and between areas;
- the background input has a fixed delay of the resolution;
- initial membrane potentials are drawn from a normal with mean −150 mV and SD 50 mV;
- neuron parameters come from `neuron_params_<type>` in `data/net.yaml`, one entry per population type; a local connection gets the excitatory or inhibitory delay by the sign of its weight, so no population name is assumed;
- connections with a weight of 0 are skipped.

## Python API

```python
from builders.humam import generate_humam_configs

paths = generate_humam_configs(
    area="rostralanteriorcingulate",
    config_dir="configs",
    network_name="humam_single",
    simulation_name="humam_single",
)
```

After generation, the model is no longer special to the simulator:

```python
from microcircuit_lab import Simulation

simulation = Simulation.from_yaml(
    network_name="humam_single",
    simulation_name="humam_single",
)
simulation.run()
```

## Package contents

- `build.py`: HuMAM source-data translation and config generation. Defines `main(argv)` (re-exported from `__init__`), the entry point `microcircuit-lab generate humam` discovers and forwards to. Ends by calling `validate_network_config` on its output.
- `data/`: bundled source data used by the builder.

New HuMAM-specific transformations belong here rather than in generic `network/` or `backends/` modules.
