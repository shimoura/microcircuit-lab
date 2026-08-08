# Microcircuit Lab

Microcircuit Lab is a configuration-driven framework for building, simulating, and analyzing recurrent neural microcircuit models. It separates **model-specific data**, **generic network representation**, and **simulator backends** so published models can share the same simulation infrastructure.

## Using this as a template for a new project

This repository is meant to be forked as the starting point for a new, independent research project: fork it, add your model under `microcircuit_lab/models/<your_model>/` (see "Adding a new model" below), and add its experiments under `experiments/<your_model>/`. A fork is not expected to track this repository going forward -- treat it as a one-time starting point, not an upstream dependency.

When forking, update `pyproject.toml`'s `name`/`description`/`authors`/`version` and this README's title to your project. The internal Python package name (`microcircuit_lab`) does not need to change -- renaming it means updating every import across the codebase for little practical benefit, since it's an internal detail nobody outside the project sees. Keep the PD14/HuMAM/toy models as working references for the schema and conventions, or delete them once your own model no longer needs the comparison.

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
│       ├── background_inputs.yaml
│       ├── stimuli.yaml   # optional
│       ├── scaling.yaml
│       └── reference.yaml
└── simulation/
    └── <simulation_name>.yaml
```

A network configuration describes biology and connectivity. A simulation configuration describes execution settings such as duration, seed, threads, and recording.

**Background input vs. stimulation.** `background_inputs.yaml` is the always-on background Poisson drive tied to `background_indegree`; it scales with `K_scaling` and is what the DC-compensation math in `network/scaling.py` accounts for. `stimuli.yaml` (optional -- omit both the file and the `stimuli:` entry in `network.yaml` if unused) describes targeted, time-limited devices for experiments instead: a constant-current pulse (`type: dc`), a Poisson train active for part of the run (`type: poisson`), or a piecewise-constant Poisson rate profile (`type: inhomogeneous_poisson`). Stimuli are not touched by scaling or compensation -- they're applied exactly as configured. See `StimulusConfig` in `microcircuit_lab/config/network.py` for the full field reference, e.g.:

```yaml
stimuli:
  - type: dc
    targets: [E]
    amplitude: 200.0   # pA
    start: 500.0        # ms
    stop: 600.0          # ms

  - type: poisson
    targets: [E, I]
    rate: 50.0           # spikes/s
    start: 200.0
    stop: 400.0
    weight: {mean: 0.15, rel_std: 0.0, distribution: fixed, unit: PSP}
    delay: {mean: 1.5, rel_std: 0.0, distribution: fixed}
```

A runnable version of this lives in `configs/network/toy_stimulated/` (the toy network plus a `stimuli.yaml`), kept separate from `configs/network/toy/` so the bundled baseline network -- used as a calibrated, unperturbed reference by several tests -- stays quiet:

```bash
python scripts/run_simulation.py --network toy_stimulated --simulation toy_stimulated
```

**Formatting convention**: hand-edited files (e.g. `configs/network/toy/`) use normal YAML block style, one field per line, for readability. Generator-written tables that can run to thousands of uniform rows (`connectivity.yaml`, and `populations.yaml`/`background_inputs.yaml` for multi-area networks) are written one-record-per-line instead -- e.g. `humam_all`'s `connectivity.yaml` is ~8,400 lines of `- {source: ..., target: ..., weight: {...}, delay: {...}}` rather than ~100,000 lines of block style, with identical parsed content. Both styles are plain YAML and load identically; use `microcircuit_lab.io.files.write_yaml`/`flow_records` in a generator to opt a field into the compact style.

## Adding a new model

There are two supported ways to try a new model, and the core package (`network/`, `simulation/`, `config/`, `io/`, `backends/`) never has to change for either one.

**Write YAML directly.** Copy `configs/network/toy/` — the smallest complete example of the schema (two populations, four connections, minimal scaling/reference) — to `configs/network/<my_model>/` and edit the values by hand. Pair it with a `configs/simulation/<my_model>.yaml` (every field has a default, so an empty file is valid). This is the right starting point for exploring a new idea or a model small enough to write out directly.

**Add a generator.** For models whose parameters come from source data (published tables, experimental recordings, pickled matrices, etc.), create `microcircuit_lab/models/<model_name>/` and keep all source-format assumptions there — the generator's job is to translate that data into the same YAML schema used above and write it under `configs/network/<model_name>/`. Follow `humam/generator.py` (full translation pipeline from bundled source data) or `pd14/generator.py` (a single derived file, rest static) depending on how much of the config is actually derived versus fixed.

If generation should be runnable from the command line, add an `add_cli(subparser)` function to the model's `generator.py` (same pattern in both examples above) and register it in `microcircuit_lab/models/__init__.py`'s `MODEL_GENERATORS`. It then becomes available as `python scripts/generate.py <model_name>` without any changes to `scripts/generate.py` itself.

**Using a neuron model other than `iaf_psc_exp`?** Every `weight` block requires a `unit` (see `WeightDistribution` in `microcircuit_lab/config/network.py`) -- deliberately no default, so a config can't silently run with the wrong conversion just because a field was left out. `PSP` (biological amplitude, mV) is converted to a simulator quantity by `NetworkPreprocessor`, but that conversion formula is currently only implemented for `iaf_psc_exp`. Rather than adding a new formula per neuron model, give your model's connections `unit: PSC` (if the weights are already current amplitudes in pA) or `unit: native` (used exactly as given, no interpretation at all -- the right choice for a conductance-based model, or anything else) instead of `PSP`. Adding a new neuron model should essentially never require touching `network/parameters.py`.

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

`prepare_output(run_dir)` and `save_recordings(run_dir)` are where recording-to-disk should be implemented in whatever way is native and efficient for that simulator (see "Run outputs" below); `get_spike_events()` should transparently read that data back regardless of how it was stored, so callers (analysis, `io/output.py`) never need backend-specific branches.

## Included models

- **PD14**: Potjans & Diesmann cortical microcircuit configuration and connectivity utilities.
- **HuMAM**: single-area and multi-area configuration generation from bundled HuMAM source data.

Model-specific documentation is located inside each package under `microcircuit_lab/models/`.

## Experiments

An experiment -- a parameter sweep, a comparison across configs, exploratory analysis for a specific model -- is a plain Python script under `experiments/<model_name>/<experiment_name>.py`. There's no dedicated framework for this beyond `Simulation`/`microcircuit_lab.analysis`: build a network config (from YAML, or with fields overridden in-memory as needed), run it, and use the same `compute_*`/`plot_*` functions as everywhere else. See `experiments/toy/background_drive_sweep.py` for a worked example (a small sweep over one population parameter, reproducing how the toy network's own background drive was calibrated).

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

Use `--network`, `--simulation`, `--area`, `--begin`, `--end`, `--reference`, `--no-raster`, and `--no-firing-rates` on `scripts/run_simulation.py` to select the network, simulation, analysis window, area, and diagnostics. Plots are saved to `<output_dir>/plots/` but not opened interactively by default; pass `--show` to also pop up the plot windows. Plot styling (colors, sizes, figure layout) is set via the `PLOT_STYLE`, `RASTER_CONFIG`, and `FIRING_RATE_CONFIG` constants at the top of the script. Generic plotting does not live inside model-specific code.

### Firing-rate distributions

After running a simulation, inspect the distribution of single-neuron firing rates within each population:

```python
from microcircuit_lab.analysis import plot_firing_rates

plot_firing_rates(simulation, begin=500.0)
```

For multi-area networks, select one area with `area="V1"`. Published reference mean rates are optional and can be overlaid with `show_reference=True`; they are hidden by default.

## Run outputs

`Simulation.run()` saves its outputs automatically, controlled by `simulation.yaml`'s `output` and `recording` sections (all optional, see `microcircuit_lab/config/simulation.py`):

```text
<output_dir>/                      # fixed if overwrite: true, else <output_dir>/<timestamp>/
├── recordings/                    # spike recordings, see below
├── config.yaml                    # the fully resolved network + simulation config actually used
└── metadata.json                  # run identity, per-population spike stats, and an artifact manifest
```

`overwrite: false` (the default, and the convention used by every bundled model) gives each run its own timestamped subdirectory, so results are never silently clobbered. Set `overwrite: true` to instead reuse the same directory every run -- convenient while iterating, but each run replaces the last one's output.

**Recordings are written by the backend, not re-serialized by microcircuit_lab.** With the NEST backend, `recordings/` is pointed at NEST's own ascii recording backend before the network is built, so NEST writes spikes straight to disk during `simulate()` -- `<population>-<id>-<thread>.dat` (one shard per thread/process, NEST's native naming and tab-separated `sender  time_ms` format). Nothing is buffered in Python memory or written twice. `Simulation`/plotting code still reads spikes back through `backend.get_spike_events(population)`, which transparently merges those shards when needed (e.g. for `metadata.json`'s statistics or `plot_raster`) -- callers never need to know recording happened natively. A backend without native file recording (or the NEST backend used standalone, without `prepare_output()`) falls back to writing one `<population>_spikes.csv` per population from the in-memory events instead.

`metadata.json`'s `artifacts` field is a single reference point listing every file the run produced, by category (`recordings`, `config`, `plots`, ...), as paths relative to the run directory -- no need to glob the directory to know what's there. `scripts/run_simulation.py` saves its raster/firing-rate plots into `<output_dir>/plots/` and registers them the same way via `microcircuit_lab.io.output.register_artifact`; any other analysis code that saves a file into the run directory should call `register_artifact(simulation.output_dir, "<category>", path)` too, so it shows up in the same manifest.

The simulation object exposes `simulation.output_dir` (a `Path`, set once `run()` has completed) for building further artifact paths.

## Testing

```bash
pytest
```

The scientific transformation functions and configuration preprocessing are tested independently from simulator execution where possible.
