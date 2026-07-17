# Microcircuit Lab

Microcircuit Lab is a configuration-driven framework for building, simulating, and analyzing recurrent neural microcircuit models. It separates **model-specific data**, **generic network representation**, and **simulator backends** so published models can share the same simulation infrastructure.

## Architecture

```text
model source data
      │
      ▼
microcircuit_lab/models/       model-specific translation and parameters
      │
      ▼
configs/network/<model>/       portable YAML network description
      │
      ▼
microcircuit_lab/config/       validated configuration schemas
      │
      ▼
microcircuit_lab/network/      network representation and preprocessing
      │
      ▼
microcircuit_lab/simulation/   high-level simulation orchestration
      │
      ▼
microcircuit_lab/backends/     simulator-specific execution
      │
      ▼
microcircuit_lab/analysis/     simulator-facing analysis and plots
```

The generic network and simulation layers do not depend on HuMAM, PD14, or any other specific reference model. Model integrations depend on the generic network utilities, never the reverse. New models should translate their source data into the common network configuration schema rather than add model-specific logic to the core.

## Project structure

```text
microcircuit_lab/
├── analysis/       # analysis and visualization
├── backends/       # simulator implementations (currently NEST)
├── config/         # validated network and simulation schemas
├── io/             # configuration file loading and validation assembly
├── models/         # model-specific integrations (HuMAM, PD14, ...)
├── network/        # generic network model, transformations, and preprocessing
└── simulation/     # high-level simulation orchestration
```

## Installation

```bash
mamba create -n microcircuit-lab python=3.12
mamba activate microcircuit-lab
pip install -e ".[dev]"
```

NEST must be available in the environment used to run simulations.

## Quick start

Run a pre-generated network configuration:

```python
from microcircuit_lab import Simulation

simulation = Simulation.from_yaml(
    network_name="pd14",
    simulation_name="default",
)
simulation.run()
```

Use `scripts/run_simulation.py` as the editable generic runner for any pre-generated network. It can produce raster and firing-rate diagnostics with one shared plot style.

## Configuration

Network and execution settings are deliberately separate:

```text
configs/
├── network/
│   └── <network_name>/
│       ├── network.yaml
│       ├── populations.yaml
│       ├── neurons.yaml
│       ├── connectivity.yaml
│       ├── inputs.yaml
│       ├── scaling.yaml
│       └── reference.yaml
└── simulation/
    └── <simulation_name>.yaml
```

A network configuration describes biology and connectivity. A simulation configuration describes execution settings such as duration, seed, threads, and recording.

## Adding a new model

Create `microcircuit_lab/models/<model_name>/` and keep all source-format assumptions there. The model integration should generate or translate data into the existing YAML network schema. Once the generic configuration exists, run it through the same public API:

```python
from microcircuit_lab import Simulation

simulation = Simulation.from_yaml(
    network_name="my_model",
    simulation_name="default",
)
simulation.run()
```

Do not add model-specific branches to `network/`, `simulation/`, or a simulator backend unless the feature is genuinely generic.

## Adding a backend

Implement the small backend contract in `microcircuit_lab/backends/base.py`, place the implementation under `backends/<name>/`, and register it in `backends.get_backend`. Then select it with:

```python
simulation = Simulation.from_yaml(
    network_name="my_model",
    simulation_name="default",
    backend="nest",
)
```

## Included models

- **PD14**: Potjans & Diesmann cortical microcircuit configuration and connectivity utilities.
- **HuMAM**: single-area and multi-area configuration generation from bundled HuMAM source data.

Model-specific documentation is located inside each package under `microcircuit_lab/models/`.

## Repository scripts

Model generation and simulation execution are intentionally separate:

```bash
python scripts/generate_humam.py --area bankssts
python scripts/run_simulation.py
```

Edit the constants at the top of `scripts/run_simulation.py` to select the network, simulation, analysis window, area, and diagnostics. Generic plotting does not live inside model-specific code.

### Firing-rate distributions

After running a simulation, inspect the distribution of single-neuron firing rates within each population:

```python
from microcircuit_lab.analysis import plot_firing_rates

plot_firing_rates(simulation, begin=500.0)
```

For multi-area networks, select one area with `area="V1"`. Published reference mean rates are optional and can be overlaid with `show_reference=True`; they are hidden by default.


## Testing

```bash
pytest
```

The scientific transformation functions and configuration preprocessing are tested independently from simulator execution where possible.
