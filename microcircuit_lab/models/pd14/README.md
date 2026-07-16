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
