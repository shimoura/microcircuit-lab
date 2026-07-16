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
microcircuit_lab/core/         validation, preprocessing, orchestration
      │
      ▼
microcircuit_lab/backends/     simulator-specific execution
      │
      ▼
microcircuit_lab/analysis/     simulator-facing analysis and plots
```

The generic core does not depend on HuMAM, PD14, or any other specific reference model. New models should translate their source data into the common network configuration schema rather than add model-specific logic to the core.

## Project structure

```text
microcircuit_lab/
├── analysis/       # analysis and visualization
├── backends/       # simulator implementations (currently NEST)
├── config/         # validated network and simulation schemas
├── core/           # generic Network, preprocessing, and Simulation
├── io/             # loading raw configuration into validated objects
├── models/         # model-specific integrations (HuMAM, PD14, ...)
└── utils/          # small generic I/O helpers
```

Legacy namespaces such as `network`, `simulation`, `backend`, `importers`, and `reference_models` remain as compatibility wrappers for existing code. New code should use the structure above.

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

The repository-level `run.py` is a small editable example that also creates a raster plot.

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

Do not add model-specific branches to `core/` or a simulator backend unless the feature is genuinely generic.

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

## Testing

```bash
pytest
```

The scientific transformation functions and configuration preprocessing are tested independently from simulator execution where possible.
