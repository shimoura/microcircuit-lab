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
- `generator.py`: derives `connectivity.yaml` from `data.py` using the PD14 connection-probability-to-synapse-count formula. It prints YAML to stdout and is not wired into a CLI script; the checked-in `configs/network/pd14/connectivity.yaml` was produced by running it. Re-run it if `data.py` changes:

```bash
python -m microcircuit_lab.models.pd14.generator > configs/network/pd14/connectivity.yaml
```
