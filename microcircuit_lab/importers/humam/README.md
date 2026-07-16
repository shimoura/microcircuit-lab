# HuMAM Config Generation

This folder includes utilities to generate simulation configs directly from HuMAM source data in `humam_data/`.

## Generate YAML configs from HuMAM data

```bash
python -m microcircuit_lab.importers.humam.config_generator \
  --area bankssts \
  --network-name humam_single \
  --simulation-name humam_single
```

This writes:

- `configs/network/humam_single/*.yaml`
- `configs/simulation/humam_single.yaml`

Optional JSON mirror output:

```bash
python -m microcircuit_lab.importers.humam.config_generator --export-json
```

## Run a single HuMAM microcircuit

Edit the variables at the top of `run_humam_single.py`, then run:

```bash
python run_humam_single.py
```

Equivalent package CLI:

```bash
python run_humam.py
```

By default `run_humam_single.py` regenerates YAML from HuMAM data before simulation.
Set `SKIP_GENERATE = True` in `run_humam_single.py` to reuse previously generated configs.

## Run all HuMAM areas (multi-area model)

Set in `run_humam_single.py`:

- `AREA = "all"`
- `NETWORK_NAME = "humam_all"`
- `SIMULATION_NAME = "humam_all"`

Then run:

```bash
python run_humam_single.py
```

Equivalent package CLI:

```bash
python run_humam.py
```

For the full model, practical simulation usually requires stronger downscaling.
Example:

Set in `run_humam_single.py`:

- `AREA = "all"`
- `NETWORK_NAME = "humam_all_small"`
- `SIMULATION_NAME = "humam_all_small"`
- `N_SCALING = 1e-5`
- `K_SCALING = 1e-5`
- `T_SIM = 100`
