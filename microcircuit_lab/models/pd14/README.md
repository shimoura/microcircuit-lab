# PD14 model integration

This package contains model-specific data and connectivity utilities for the Potjans & Diesmann (2014) cortical microcircuit.

The runnable PD14 network is stored as generic configuration under `configs/network/pd14/`. It therefore uses the same simulation path as any other model:

```python
from microcircuit_lab import Simulation

simulation = Simulation.from_yaml(
    network_name="pd14",
    simulation_name="default",
)
simulation.run()
```

Keep PD14-specific constants and translation logic in this package. Generic scaling, configuration processing, and simulator execution belong in the shared framework layers.

## Package contents

- `data.py`: raw PD14 population sizes and connection probabilities.
- `generator.py`: derives `connectivity.yaml` from `data.py` using the PD14 connection-probability-to-synapse-count formula (shared with other models via `microcircuit_lab.network.connectivity.num_synapses_from_conn_prob`). Only `connectivity.yaml` is generated; the other PD14 network files (populations, neurons, inputs, scaling, reference) are static and checked in directly. Exposes `add_cli()`, which registers this model's arguments on the shared `scripts/generate.py` dispatcher (see `microcircuit_lab.models.MODEL_GENERATORS`).

The checked-in `configs/network/pd14/connectivity.yaml` was produced by this generator. Re-run it if `data.py` changes:

```bash
python scripts/generate.py pd14
```
