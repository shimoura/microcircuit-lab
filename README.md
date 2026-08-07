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

The fastest way to see the framework run is the bundled `toy` network — a minimal two-population (E/I) example under `configs/network/toy/`:

```python
from microcircuit_lab import Simulation

simulation = Simulation.from_yaml()  # defaults to network_name="toy", simulation_name="toy"
simulation.run()
```

Or run a published reference model the same way:

```python
from microcircuit_lab import Simulation

simulation = Simulation.from_yaml(
    network_name="pd14",
    simulation_name="default",
)
simulation.run()
```

Use `scripts/run_simulation.py` as the editable generic runner for any pre-generated network (defaults to `pd14`; pass `--network toy --simulation toy` for the minimal example). It can produce raster and firing-rate diagnostics with one shared plot style. Use `scripts/generate.py <model>` to (re)generate a model's network configuration.

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

There are two supported ways to try a new model, and the core package (`network/`, `simulation/`, `config/`, `io/`, `backends/`) never has to change for either one.

**Write YAML directly.** Copy `configs/network/toy/` — the smallest complete example of the schema (two populations, four connections, minimal scaling/reference) — to `configs/network/<my_model>/` and edit the values by hand. Pair it with a `configs/simulation/<my_model>.yaml` (every field has a default, so an empty file is valid). This is the right starting point for exploring a new idea or a model small enough to write out directly.

**Add a generator.** For models whose parameters come from source data (published tables, experimental recordings, pickled matrices, etc.), create `microcircuit_lab/models/<model_name>/` and keep all source-format assumptions there — the generator's job is to translate that data into the same YAML schema used above and write it under `configs/network/<model_name>/`. Follow `humam/generator.py` (full translation pipeline from bundled source data) or `pd14/generator.py` (a single derived file, rest static) depending on how much of the config is actually derived versus fixed.

If generation should be runnable from the command line, add an `add_cli(subparser)` function to the model's `generator.py` (same pattern in both examples above) and register it in `microcircuit_lab/models/__init__.py`'s `MODEL_GENERATORS`. It then becomes available as `python scripts/generate.py <model_name>` without any changes to `scripts/generate.py` itself.

Either way, once the generic configuration exists, run it through the same public API:

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

Model generation and simulation execution are intentionally separate: `scripts/generate.py` produces a model's config files, and `scripts/run_simulation.py` runs any pre-generated config by name. Neither script contains model-specific logic, so both stay unchanged as models are added.

Run the bundled PD14 network (uses the default network/simulation names):

```bash
python scripts/run_simulation.py
```

Generate a HuMAM network, then run it by name:

```bash
python scripts/generate.py humam --area bankssts
python scripts/run_simulation.py --network humam_single --simulation humam_single
```

Regenerate PD14's connectivity from source data (its other config files are static):

```bash
python scripts/generate.py pd14
```

Every registered model's generation arguments are discoverable with `python scripts/generate.py <model> --help`.

Use `--network`, `--simulation`, `--area`, `--begin`, `--end`, `--reference`, `--no-raster`, and `--no-firing-rates` on `scripts/run_simulation.py` to select the network, simulation, analysis window, area, and diagnostics. Plot styling (colors, sizes, figure layout) is set via the `PLOT_STYLE`, `RASTER_CONFIG`, and `FIRING_RATE_CONFIG` constants at the top of the script. Generic plotting does not live inside model-specific code.

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
