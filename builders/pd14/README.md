# PD14 model integration

This package contains model-specific data and connectivity utilities for the Potjans & Diesmann (2014) cortical microcircuit.

The runnable PD14 network is stored as generic configuration under `configs/network/pd14/`. It therefore uses the same simulation path as any other model:

```python
from microcircuit_lab import Simulation

simulation = Simulation.from_yaml(
    network_name="pd14",
    simulation_name="pd14",
)
simulation.run()
```

Keep PD14-specific constants and translation logic in this package. Generic scaling, configuration processing, and simulator execution belong in the shared framework layers.

## Package contents

- `data.py`: the PD14 parameters, with their sources: Potjans & Diesmann (2014), *Cerebral Cortex* 24:785–806, and the official PyNEST implementation ([INM-6/microcircuit-PD14-model](https://github.com/INM-6/microcircuit-PD14-model), commit `f79f8ac`, `network_params.py`). The optimized initial membrane potentials and the reference rates come from the official implementation only.
- `build.py`: writes the whole `configs/network/pd14/` directory from `data.py` (connection probabilities are converted to synapse numbers with `microcircuit_lab.network.connectivity.num_synapses_from_conn_prob`). Defines `main(argv)` (re-exported from `__init__`), the entry point `microcircuit-lab generate pd14` discovers and forwards to.

The checked-in `configs/network/pd14/` and `configs/network/pd14_dc/` were produced by this builder. Re-run it if `data.py` changes:

```bash
microcircuit-lab generate pd14
microcircuit-lab generate pd14 --network-name pd14_dc --background-mode dc
```

`--background-mode dc` replaces the Poisson background by a constant current of equal mean (the publication's Fig. 5 comparison).
