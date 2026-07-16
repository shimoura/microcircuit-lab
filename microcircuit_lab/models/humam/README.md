# HuMAM model integration

This package translates HuMAM source data into Microcircuit Lab's generic network configuration format. HuMAM-specific data handling stays here; simulation is handled by the generic core and selected backend.

## Generate and run

From the repository root:

```bash
python run_humam.py --area bankssts
```

For the multi-area model:

```bash
python run_humam.py --area all
```

The command generates configurations under `configs/network/` and `configs/simulation/`, then runs them through `microcircuit_lab.Simulation`.

Use `--skip-generate` to reuse existing generated configurations. Run `python run_humam.py --help` for the available scaling, duration, seed, thread, and output options.

## Python API

```python
from microcircuit_lab.models.humam import generate_humam_configs

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

- `generator.py`: HuMAM source-data translation and config generation.
- `data/`: bundled source data used by the generator.

New HuMAM-specific transformations belong here rather than in generic `network/` or `backends/` modules.
