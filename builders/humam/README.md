# HuMAM model integration

This package translates HuMAM source data into Microcircuit Lab's generic network configuration format. HuMAM-specific data handling stays here; simulation is handled by the generic core and selected backend.

## Generate and run

From the repository root:

```bash
microcircuit-lab generate humam --area bankssts
```

For the multi-area model:

```bash
microcircuit-lab generate humam --area all
```

The command generates configurations under `configs/network/` and `configs/simulation/`.

Generation only writes portable configuration files. Run them separately with `microcircuit-lab run`. Use `microcircuit-lab generate humam --help` for the available generation options.

## Python API

```python
from builders.humam import generate_humam_configs

paths = generate_humam_configs(
    area="bankssts",
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
