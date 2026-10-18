# Microcircuit Lab

Microcircuit Lab is a configuration-driven framework for building, simulating, and analyzing recurrent neural microcircuit models. It separates **model-specific data**, **generic network representation**, and **simulator backends** so published models can share the same simulation infrastructure.

## Contents

- [Using this as a template for a new project](#using-this-as-a-template-for-a-new-project)
- [Architecture](#architecture)
- [Project structure](#project-structure)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Scaling a network](#scaling-a-network)
- [Adding a new model](#adding-a-new-model)
- [Adding a backend](#adding-a-backend)
- [Using a NESTML model](#using-a-nestml-model)
- [Included models](#included-models)
- [Experiments](#experiments)
- [Repository scripts](#repository-scripts)
- [Run outputs](#run-outputs)
- [Analysing a run](#analysing-a-run)
- [Testing](#testing)

## Using this as a template for a new project

This repository is meant to be forked as the starting point for a new, independent research project. A fork is not expected to track this repository going forward -- treat it as a one-time starting point, not an upstream dependency.

1. Fork the repository.
2. Update `pyproject.toml`'s `name`/`description`/`authors`/`version` to your project.
3. Replace the root `README.md` with a short description of your own project -- it's meant to be overwritten. Leave this file (`microcircuit_lab/README.md`) as-is; it's the framework reference and stays accurate across forks.
4. Add your model under `builders/<your_model>/` (see [Adding a new model](#adding-a-new-model)).
5. Add its experiments under `experiments/<your_model>/` (see [Experiments](#experiments)).
6. Keep the PD14/HuMAM/toy models as working references for the schema and conventions, or delete them once your own model no longer needs the comparison.

The internal Python package name (`microcircuit_lab`) does not need to change -- renaming it means updating every import across the codebase for little practical benefit, since it's an internal detail nobody outside the project sees.

## Architecture

```text
model source data
      │
      ▼
builders/                      model-specific translation and parameters
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

The generic network and simulation layers do not depend on HuMAM, PD14, or any other specific reference model. Builders depend on the generic network utilities, never the reverse. New models should translate their source data into the common network configuration schema rather than add model-specific logic to the core.

## Project structure

```text
microcircuit_lab/
├── analysis/       # analysis and visualization
├── backends/       # simulator implementations (currently NEST)
├── config/         # validated network and simulation schemas
├── io/             # configuration file loading and validation assembly
├── network/        # generic network model, transformations, and preprocessing
└── simulation/     # high-level simulation orchestration

builders/           # model-specific builders (HuMAM, PD14, ...), outside the package
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

If you'd rather manage the environment with mamba/conda:

```bash
mamba create -n microcircuit-lab python=3.12
mamba activate microcircuit-lab
pip install -e ".[dev]"
```

**NEST.** This package doesn't pin NEST as a hard dependency, since how you get it depends heavily on where you run: install the PyPI package with `pip install -e ".[dev,nest]"`, get it from conda-forge (`mamba install -c conda-forge nest-simulator`), or build it from source (common on clusters, e.g. for MPI or a site-specific compiler toolchain). Whichever route you use, all that matters is that `import nest` works in the environment you run simulations in -- see the [NEST installation docs](https://nest-simulator.readthedocs.io/en/stable/installation/index.html) for the source-build instructions.

## Quick start

The fastest way to see the framework run is the bundled `toy` network, a minimal two-population (E/I) example under `configs/network/toy/`:

```bash
python scripts/run_simulation.py --network toy
```

`scripts/run_simulation.py` is the generic runner for any pre-generated network (defaults to `pd14`; `--simulation`/`--analysis` default to whatever `--network` is set to, see [Configuration](#configuration)). It produces raster, firing-rate, power-spectrum, and ISI-CV diagnostics with one shared plot style. Use `scripts/generate.py <model>` to (re)generate a model's network configuration.

The same thing from Python, e.g. for a notebook or a script under `experiments/`:

```python
from microcircuit_lab import Simulation

simulation = Simulation.from_yaml()  # defaults to network_name="toy", simulation_name="toy"
simulation.run()
```

Swap in a published reference model by passing its name: `Simulation.from_yaml(network_name="pd14")`.

## Configuration

Network, execution, and analysis/plot settings are deliberately separate:

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
├── simulation/
│   └── <simulation_name>.yaml
└── analysis/
    └── <analysis_name>.yaml   # optional
```

`microcircuit_lab/config/schema.py` is the field reference: one short model per file, listing every field with its type and constraints. A field with no default is required; one with `Field(default=...)` is optional and shows its default. `configs/network/toy/` is that same schema as a small working network to copy.

A network configuration describes biology and connectivity. A simulation configuration describes execution settings such as duration, seed, threads, and recording. An analysis configuration (`AnalysisConfig`, `microcircuit_lab/config/analysis.py`) describes presentation only -- which diagnostic plots run, the time window/area to analyze, and their styling (colors, figure sizes, raster neuron subsampling, ...); it has no effect on the simulation itself.

Each network file has a schema in `microcircuit_lab/config/schema.py` (one model per file), and `read_network_directory` validates against it on every load -- so a missing, misspelled, or wrong-typed field fails with the file and field named, the moment a config is loaded (to run it) or written (by a builder), not later as a `KeyError`. Cross-file references (a population's neuron, a connection's populations) and the preprocessing step are checked the same way. The one open spot is a neuron's `parameters:` block -- neuron models differ in what they accept, so the simulator backend, not the schema, is the authority on those names. `microcircuit_lab.io.validate_network_config(dir)` runs the whole check on its own if you want it without a run.

These are three independent trees, matched by name, so one network can be paired with more than one execution profile or presentation (e.g. a short simulation for a quick check vs. a long one for a real run; a quick raster-only look vs. a full styled figure set for a paper). In the common case where a network only ever has one of each, `Simulation.from_yaml(network_name=...)` and `AnalysisConfig.from_yaml(network_name=...)` alone are enough: `simulation_name`/`analysis_name` both default to whatever `network_name` is, so `configs/network/toy/` pairs automatically with `configs/simulation/toy.yaml` and `configs/analysis/toy.yaml`. Pass `simulation_name`/`analysis_name` explicitly only when you want a different, decoupled profile.

Unlike network/simulation configs, an analysis config is optional: if `configs/analysis/<name>.yaml` doesn't exist, `AnalysisConfig.from_yaml` falls back to built-in defaults rather than raising, so adding a new network never requires an analysis file. Because `AnalysisConfig`/`PlotStyle`/`RasterPlotConfig`/etc. are just pydantic models, a one-off tweak for a specific script or notebook doesn't need a YAML file at all -- override in memory instead, e.g. `plot_raster(sim, config=RasterPlotConfig(neuron_fraction=0.05))`. Save a variant to YAML only once it's a default worth reusing; see [Experiments](#experiments) for where a one-off analysis script belongs instead.

Beyond `begin`/`end`/`area`/`show_reference`/`style`, `AnalysisConfig` doesn't pre-declare a field per plot -- `raster:`/`firing_rates:`/`power_spectrum:`/`isi_cv:` are just the top-level sections the four bundled diagnostics happen to be registered under (see [Adding a new diagnostic](#adding-a-new-diagnostic)). A section name that isn't registered raises a clear error rather than being silently ignored.

**Background input vs. stimulation.** `background_inputs.yaml` is the always-on background Poisson drive tied to `background_indegree`; it scales with `K_scaling` and is what the DC-compensation math in `network/scaling.py` accounts for.

`stimuli.yaml` (optional -- omit both the file and the `stimuli:` entry in `network.yaml` if unused) describes targeted, time-limited devices for experiments instead:

- `type: dc` -- a constant-current pulse
- `type: poisson` -- a Poisson train active for part of the run
- `type: inhomogeneous_poisson` -- a piecewise-constant Poisson rate profile

Stimuli are not touched by scaling or compensation -- they're applied exactly as configured. See `StimulusConfig` in `microcircuit_lab/config/network.py` for the full field reference, e.g.:

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

**Poisson vs. DC background.** Add a top-level `background_mode: dc` to `background_inputs.yaml` (default is `poisson`) to replace the background Poisson generator network-wide with a constant current of equal mean, reproducing Potjans & Diesmann (2014)'s comparison of the two drive types (their Fig. 5) -- see `configs/network/pd14_dc/` for a ready-to-run example (`--network pd14_dc`, pairs with `configs/simulation/pd14_dc.yaml`) and `NetworkConfig.background_mode` / `NetworkPreprocessor._apply_background_dc_current` for the implementation.

**Weights and delays outside their range.** A normal weight keeps the sign of its mean and a delay must not be shorter than a minimum, but a random draw can break both. Add a top-level `bound_mode` to `connectivity.yaml` to choose what happens to such a draw, for every weight and delay of the network (background inputs and stimuli included): `redraw` (default) draws again until the value is allowed; `clip` replaces it by the limit (a weight of the wrong sign becomes 0, a short delay becomes the minimum), as the HuMAM model does. The smallest allowed delay of a drawn delay is half the simulation step unless a `delay` sets its own `minimum` (in ms, for example `minimum: 0.1`); a smaller `minimum` is raised to half the step, and a `fixed` delay keeps its value.

**Inhibitory synapses and the scaling compensation.** When `K_scaling` is below 1 the compensation current, and the DC current of `background_mode: dc`, use `tau_syn_ex` for excitatory input and `tau_syn_in` for inhibitory input, recurrent or background (an input is inhibitory when its PSC is negative). The two only differ when the neuron's `tau_syn_in` differs from `tau_syn_ex`.

**Weight units.** Every `weight` block requires a `unit` (see `WeightDistribution` in `microcircuit_lab/config/network.py`) -- deliberately no default, so a config can't silently run with the wrong conversion just because a field was left out.

`PSP` (biological amplitude, mV) is converted to a current amplitude by `NetworkPreprocessor`. That conversion (`network/synapses.py`) only depends on the target neuron having `C_m`, `tau_m`, `tau_syn_ex` and `tau_syn_in` parameters, not on the model's name -- it applies to any current-based LIF neuron with single-exponential synaptic currents, `iaf_psc_exp` is just the model most people know it from. This module has no notion of "simulator" or "backend", so it can't check the model's actual dynamics for you: giving `unit: PSP` to a neuron that happens to have those four parameter names without actually having this dynamics will silently produce the wrong weight. That's on whoever writes the config, the same way `unit: PSC`/`unit: native` are already explicit choices.

For a genuinely different model (a conductance-based one, an adaptive-exponential one, or anything else), give its connections `unit: PSC` (if the weights are already current amplitudes in pA) or `unit: native` (used exactly as given, no interpretation at all) instead of `PSP`. Adding a new neuron model should essentially never require touching `network/parameters.py`.

If your model has this dynamics but names its parameters differently, set `psp_conversion_aliases` on its `neurons.yaml` entry instead of renaming anything (the parameter names in `parameters:` have to stay whatever your model actually accepts):

```yaml
neurons:
  my_model:
    model: some_custom_model_name
    parameters:
      Cm: 250.0
      tau_membrane: 10.0
      tau_exc: 2.0
      tau_inh: 2.0
      # ... whatever else your model needs
    psp_conversion_aliases:
      C_m: Cm
      tau_m: tau_membrane
      tau_syn_ex: tau_exc
      tau_syn_in: tau_inh
```

Only list the names that actually differ; an omitted key falls back to the canonical name unchanged. A compiled NESTML model is the most common case this solves; see [Using a NESTML model](#using-a-nestml-model).

**Formatting convention**: hand-edited files (e.g. `configs/network/toy/`) use normal YAML block style, one field per line, for readability. Builder-written tables that can run to thousands of uniform rows (`connectivity.yaml`, and `populations.yaml`/`background_inputs.yaml` for multi-area networks) are written one-record-per-line instead -- e.g. `humam_all`'s `connectivity.yaml` is ~8,400 lines of `- {source: ..., target: ..., weight: {...}, delay: {...}}` rather than ~100,000 lines of block style, with identical parsed content. Both styles are plain YAML and load identically; `microcircuit_lab.io.write_network_directory` applies the compact style to `populations`, `connectivity`, and `background_inputs` automatically, or use `microcircuit_lab.io.files.write_yaml`/`flow_records` directly to opt a field in.

## Scaling a network

A full-scale network can be slow or need a lot of memory. `scaling.yaml` runs a smaller copy:

```yaml
N_scaling: 0.1   # keep 10 % of the neurons of every population
K_scaling: 0.1   # keep 10 % of the connections each neuron receives (the indegree)
```

Both default to 1 (no scaling). Fewer connections means less input, so the weights are made stronger and a constant current (DC) is added to give each neuron back the mean input it lost. The other options choose how:

| `preserve_variance` | `preserve_mean_input` | `compensate_recurrent_input` | What happens |
|---|---|---|---|
| true | true | true | **Default.** Weights are divided by √`K_scaling`, which keeps the size of the input fluctuations. A DC current replaces the mean input lost from the recurrent and the background connections. |
| true | true | false | Same weights. The DC replaces only the lost background input. |
| true | false | (ignored) | Same weights, no DC. The mean input is lower than in the full network. |
| false | (ignored) | (ignored) | Weights are divided by `K_scaling`, which keeps the mean input but increases the fluctuations. No DC. |

The recurrent part of the DC is computed from the full-scale mean rates, so `reference.yaml` needs `full_mean_rates` for every population; a missing one raises an error that names it. Set `compensate_recurrent_input: false` to compensate only the background, or `preserve_mean_input: false` to scale without a DC. Inhibitory input is compensated with `tau_syn_in` and excitatory input with `tau_syn_ex`. A connection that ends up with less than one synapse after scaling is dropped.

Example, PD14 at `N_scaling = K_scaling = 0.1`: without the DC, two populations are silent; with it, most rates are within 10-20 % of the full-scale values (L2/3 E is lower, 0.45 Hz instead of 0.9 Hz). The DC restores the mean input, not the fluctuations, so a downscaled network never reproduces the full one exactly.

## Adding a new model

There are two ways to add a model, and the core package (`network/`, `simulation/`, `config/`, `io/`, `backends/`) never changes for either one. Both produce the same thing: a `configs/network/<model>/` directory matching the schema in `microcircuit_lab/config/schema.py`. That directory is validated automatically whenever it is loaded -- so a mistake surfaces the first time you run the network (or generate it), with the file and field named.

### Option A: write YAML directly

Best for exploring a new idea or a model small enough to write out by hand.

1. Copy `configs/network/toy/` to `configs/network/<my_model>/` -- a small working example, one comment per file. `microcircuit_lab/config/schema.py` is the full field list (types, defaults, which are required).
2. Edit the values in `configs/network/<my_model>/*.yaml` by hand.
3. Optionally add `configs/simulation/<my_model>.yaml` to change execution settings (simulated time, threads, what to record -- `microcircuit_lab/config/simulation.py` is the field list). Leave it out and the built-in `SimulationConfig` defaults are used, same as a missing `configs/analysis/<my_model>.yaml`.
4. `python scripts/run_simulation.py --network <my_model>` -- loading the config validates every file; fix anything it reports.

### Option B: add a builder

Best for a model whose parameters come from source data (published tables, experimental recordings, pickled matrices, etc.). A builder is **any code that writes a valid `configs/network/<model>/`** -- a script, a notebook, whatever. Each folder in `builders/` turns one model's data into a network description under `configs/network/`. The only thing the shared `python scripts/generate.py <model>` CLI needs (run from the repository root) is a `builders/<model>/` package exposing a callable `main(argv=None)`; it is then discovered automatically, with no list to edit. A builder that lives in another installed package can register its `main` under the `microcircuit_lab.builders` entry-point group instead (see `microcircuit_lab/io/builders.py`).

1. `python scripts/new_builder.py <model_name>` creates `builders/<model_name>/__init__.py` with a runnable `main()` that writes a small example network -- replace its values with your model's. Add a `README.md` and `tests/test_<model_name>.py` yourself.
2. Implement `main()`: read your source data (put it under the package, e.g. a `data/` dir or a `data.py` like `pd14`), build the parts, and pass them to `microcircuit_lab.io.write_network_directory(<config_dir>/network/<model_name>, populations=..., neurons=..., connections=..., background_inputs=...)` -- it writes every file and validates the result, raising with the file and field named if a mistake slipped in. `microcircuit_lab/config/schema.py` is the field list; `microcircuit_lab.io` also has `weight(...)`/`delay(...)` for the repeated `weight`/`delay` dicts; `builders/pd14/` and `builders/humam/` are worked builders.
3. `python scripts/generate.py <model_name>` -- or `python scripts/generate.py` with no arguments to confirm it was discovered.

### Run it

Either way, once the config exists under `configs/network/<my_model>/`, run it through the same public API:

```python
from microcircuit_lab import Simulation

simulation = Simulation.from_yaml(network_name="my_model")
simulation.run()
```

or from the CLI: `python scripts/run_simulation.py --network my_model`.

Do not add model-specific branches to `network/`, `simulation/`, or a simulator backend unless the feature is genuinely generic.

## Adding a backend

1. Implement the `SimulationBackend` contract from `microcircuit_lab/backends/base.py` under a new `microcircuit_lab/backends/<name>/` package.
   - `prepare_output(run_dir)` and `save_recordings(run_dir)` are where recording-to-disk should happen, in whatever way is native and efficient for that simulator (see [Run outputs](#run-outputs)).
   - `get_spike_events()` should transparently read that data back regardless of how it was stored, so callers (analysis, `io/output.py`) never need backend-specific branches.
   - The constructor isn't limited to `(network, simulation_config)`: it can accept additional keyword-only arguments for whatever it alone needs. `NestBackend`'s `extension_modules` is the existing example; see [Using a NESTML model](#using-a-nestml-model) for it in context.
2. Register the backend in `backends.get_backend` (`microcircuit_lab/backends/__init__.py`).
3. Select it by name, passing any backend-specific arguments through `backend_options` -- `Simulation`/`config`/`network` never inspect those:

```python
simulation = Simulation.from_yaml(
    network_name="my_model",
    backend="nest",
    backend_options={},  # backend-specific kwargs, e.g. extension_modules for NEST
)
```

## Using a NESTML model

NESTML compiles a custom neuron model into a NEST extension module, loaded at runtime with `nest.Install(module_name)` before any node using that model can be created. This is entirely a capability of `NestBackend` (its `extension_modules` constructor argument, see [Adding a backend](#adding-a-backend)); nothing elsewhere in the package has any notion of NESTML.

1. **Write the `.nestml` source** under a top-level `nestml/` directory, parallel to `configs/` -- not inside `builders/`, since nothing reads a `.nestml` file at runtime (NESTML's own compiler does) and a compiled module is platform/NEST-version-specific, not something to ship as package data. A model reusable across networks can sit flat in `nestml/`; one written specifically for a given model gets its own `nestml/<model_name>/` subdirectory, the same convention used by `configs/network/<model>/` and `experiments/<model>/`:

   ```text
   nestml/
   ├── generic_lif.nestml           # reusable across networks
   └── humam/
       └── humam_lif.nestml         # written specifically for the HuMAM reproduction
   ```

   Compiled output is gitignored, like `output/`.

2. **Compile it**, once, ahead of time, with NESTML's own tooling (same idea for a model-specific file under `nestml/<model_name>/`, just with that path instead):

   ```python
   from pynestml.frontend.pynestml_frontend import generate_nest_target

   generate_nest_target(
       input_path="nestml/generic_lif.nestml",
       target_path="nestml/build/my_module",
       module_name="my_module",
   )
   ```

   This registers the model under whatever name your `.nestml` file (or NESTML's default suffixing) gives it, e.g. `generic_lif_nestml`.

3. **Reference the compiled model in a network config.** From here it's just another neuron model as far as `neurons.yaml` is concerned: use that name as `model`, its own parameters as `parameters`, and `psp_conversion_aliases` if you're using `unit: PSP` and it names things differently (see [Configuration](#configuration)). To try it against a network you already trust, copy rather than edit in place, e.g. `configs/network/toy/` to `configs/network/toy_nestml/` -- the same way `toy_stimulated` was kept separate from `toy`.

4. **Load the compiled module before building the network.** This is the only NEST-specific step, and it's `NestBackend`'s `extension_modules` from [Adding a backend](#adding-a-backend):

   ```python
   from microcircuit_lab import Simulation

   simulation = Simulation.from_yaml(
       network_name="toy_nestml",
       simulation_name="toy_nestml",
       backend="nest",
       backend_options={"extension_modules": ["my_module"]},
   )
   simulation.run()
   ```

   `extension_modules` is loaded fresh on every `run()`, in `NestBackend.initialize()`, before populations are created.

## Included models

- **PD14**: Potjans & Diesmann cortical microcircuit configuration and connectivity utilities.
- **HuMAM**: single-area and multi-area configuration generation from bundled HuMAM source data.

Model-specific documentation is located inside each folder under `builders/`.

## Experiments

An experiment -- a parameter sweep, or a comparison across configs -- is a plain Python script under `experiments/<model_name>/<experiment_name>.py` that runs simulations itself. There's no dedicated framework for this beyond `Simulation`/`microcircuit_lab.analysis`: build a network config (from YAML, or with fields overridden in-memory as needed), run it, and use the same `compute_*`/`plot_*` functions as everywhere else. See `experiments/toy/background_drive_sweep.py` for a worked example (a small sweep over one population parameter, reproducing how the toy network's own background drive was calibrated). To analyse a run you already have, see [Analysing a run](#analysing-a-run).

### Re-plotting without re-simulating

A run already saves everything a plot needs (`config.yaml`, `recordings/`), so trying a different `--begin`/`--end`/`--area`/analysis profile on a run you already have doesn't require re-simulating it. Pass `--run-dir` instead of `--network`/`--simulation`; every other flag above works the same:

```bash
python scripts/run_simulation.py --network toy   # prints "Run directory: ..."
python scripts/run_simulation.py --run-dir output/toy/<timestamp> --begin 200 --end 400
```

Plots are written back into that same run's own `plots/` directory. Programmatically, this is `Simulation.from_run_dir(run_dir)` -- it returns a `Simulation` with a working `.backend` (reading spikes back from `recordings/` instead of a live NEST process, via `PostHocBackend`) without ever calling `.run()`, so `microcircuit_lab.analysis`'s `plot_*`/`compute_*` functions work on it exactly as they do on a freshly-run one. Only runs saved after this feature was added carry the `first_gid` metadata field it needs; an older run raises a clear error instead of silently reconstructing the wrong neuron IDs -- just re-run it once to pick up the new field.

### Adding a bundled plot (package maintainers)

Adding a bundled plot (raster, firing rates, power spectrum and ISI CV are the current four) doesn't touch `AnalysisConfig`, any `__init__.py` export list, or `scripts/run_simulation.py` -- it's a registry, the same pattern already used for simulator backends (`backends.get_backend`), model builders (`io.discover_builders`), and spectral estimators (`power_spectrum.POWER_SPECTRUM_METHODS`). Write the plot function and a small config class for its settings, then register it once:

```python
from microcircuit_lab.analysis import register_plot

register_plot(
    "spectrogram",
    plot_spectrogram,
    config_cls=SpectrogramPlotConfig,
    filename="spectrogram.png",
)
```

That's the entire wiring:

- `scripts/run_simulation.py` gets a `--spectrogram`/`--no-spectrogram` flag automatically (it builds its CLI by looping over `microcircuit_lab.analysis.PLOT_REGISTRY`)
- `configs/analysis/*.yaml` files don't need to change shape at all -- a `spectrogram:` top-level section works exactly like `raster:`/`firing_rates:` already do (an unregistered section name raises a clear error instead of being silently ignored, via `check_unknown_plot_sections`)

For a plot in your own project, not in this package, see [Analysing a run](#analysing-a-run).

### Firing-rate distributions

After running a simulation, inspect the distribution of single-neuron firing rates within each population:

```python
from microcircuit_lab.analysis import plot_firing_rates

plot_firing_rates(simulation, begin=500.0)
```

For multi-area networks, select one area with `area="V1"`; `list_areas(simulation)` returns the available area names. The string `"all"` is only understood by `scripts/run_simulation.py` (which loops over the areas); the plot functions themselves take one area at a time. Published reference mean rates are optional and can be overlaid with `show_reference=True`; they are hidden by default.

## Run outputs

`Simulation.run()` saves its outputs automatically, controlled by `simulation.yaml`'s `output` and `recording` sections (all optional, see `microcircuit_lab/config/simulation.py`):

```text
<output_dir>/                      # fixed if overwrite: true, else <output_dir>/<timestamp>/
├── recordings/                    # spike recordings, see below
├── config.yaml                    # the fully resolved network + simulation config actually used
└── metadata.json                  # run identity, per-population spike stats, and an artifact manifest
```

`overwrite: false` (the default, and the convention used by every bundled model) gives each run its own timestamped subdirectory, so results are never silently clobbered. Set `overwrite: true` to instead reuse the same directory every run -- convenient while iterating, but each run replaces the last one's output.

**Recordings are written by the backend, not re-serialized by microcircuit_lab.** With the NEST backend, `recordings/` is pointed at NEST's own ascii recording backend before the network is built, so NEST writes spikes straight to disk during `simulate()`: `spikes-<id>-<thread>.dat`, one shard per thread/process, NEST's native naming and tab-separated `sender  time_ms` format. Nothing is buffered in Python memory or written twice.

`Simulation`/plotting code still reads spikes back through `backend.get_spike_events(population)`, which transparently merges those shards and slices by GID range when needed (e.g. for `metadata.json`'s statistics or `plot_raster`) -- callers never need to know recording happened natively. A backend without native file recording (or the NEST backend used standalone, without `prepare_output()`) falls back to writing a consolidated `spikes.csv` from the in-memory events instead.

Voltage recording (`recording.voltage_recording: true`) uses one shared multimeter the same way and writes `voltage-<id>-<thread>.dat`. By default it records only the first 5 neurons of each population (`recording.voltage_sample_size: 5`), which keeps memory and file sizes small on large networks; set another number `N` to change that, or `null` to record every neuron.

`metadata.json`'s `artifacts` field is a single reference point listing every file the run produced, by category (`recordings`, `config`, `plots`, ...), as paths relative to the run directory -- no need to glob the directory to know what's there. `scripts/run_simulation.py` saves its raster/firing-rate plots into `<output_dir>/plots/` and registers them the same way via `microcircuit_lab.io.output.register_artifact`. Any other analysis code that saves a file into the run directory should call `register_artifact(simulation.output_dir, "<category>", path)` too, so it shows up in the same manifest.

The simulation object exposes `simulation.output_dir` (a `Path`, set once `run()` has completed) for building further artifact paths.

## Analysing a run

Every run writes a *run folder* (`output/<model>/<timestamp>/`, see above) that holds its config and its spike recordings. An analysis is any Python code that opens a run folder, computes what you want, and saves files back into it. How you do the middle part is up to you, as for builders.

### Write an analysis

Put a file in an `analyses/` folder next to `configs/` and `builders/`:

```python
# analyses/rate_bars.py
import sys

import matplotlib.pyplot as plt

from microcircuit_lab import Simulation
from microcircuit_lab.analysis import compute_population_firing_rates, register_plot
from microcircuit_lab.io.output import register_artifact


def rate_bars(simulation, save_path, area=None):
    """Mean rate of each population, as bars."""
    rates = compute_population_firing_rates(simulation, area=area)
    fig, ax = plt.subplots()
    ax.bar(list(rates), list(rates.values()))
    ax.set_ylabel("Rate (spikes/s)")
    fig.savefig(save_path)


register_plot("rate_bars", rate_bars)


if __name__ == "__main__":
    simulation = Simulation.from_run_dir(sys.argv[1])
    path = simulation.output_dir / "plots" / "rate_bars.png"
    path.parent.mkdir(exist_ok=True)
    rate_bars(simulation, path)
    register_artifact(simulation.output_dir, "plots", path)
```

The file works in two ways, and you can use either or both:

- **Run it yourself** on any run folder. Nothing else is needed:
  ```bash
  python analyses/rate_bars.py output/my_model/<timestamp>
  ```
  `Simulation.from_run_dir` opens the finished run without re-simulating it. The last line lists the new file in the run's `metadata.json`.
- **Let `run_simulation.py` run it.** The line `register_plot("rate_bars", rate_bars)` gives you a `--rate-bars` flag and, in the analysis YAML, a `rate_bars:` section. With `--area all` you get one figure per area, saved under `plots/` and listed in `metadata.json`:
  ```bash
  python scripts/run_simulation.py --run-dir output/my_model/<timestamp> --rate-bars
  ```
  The script imports every file in `analyses/` before it reads its flags, so run it from the project folder. Because of the `if __name__ == "__main__":` line, the standalone part does not run when the script imports the file.

### What your function can ask for

The first parameter is always the simulation. After that, name only what you need, and `run_simulation.py` fills it in:

| Parameter | What you get |
|---|---|
| `save_path` | where to save the figure (the script creates the folder) |
| `area` | one area name, or `None` for single-area networks |
| `begin`, `end` | the time window in ms (`--begin`, `--end`) |
| `style` | the shared plot style; `population_color(name, index, style)` and `population_label(name, style)` use it |
| `config` | your settings: the `rate_bars:` section of the analysis YAML, as a plain dict (`{"enabled": true, "color": "green"}`) |
| `show` | `True` with `--show` |
| `show_reference` | `True` if reference rates should be overlaid (`--reference`) |

A parameter with any other name must have a default value, as `area=None` has above. If it doesn't, `register_plot` fails at once and lists the names you can use.

A plot registered like this is off by default. Pass `--rate-bars`, or set `enabled: true` in the `rate_bars:` section, to switch it on.

### Good to know

- A name that is already used raises an error, so a plot of yours cannot replace `raster` or another bundled plot.
- To make `--area all` work, use `area` when you pick populations: `select_populations(simulation, None, area)` returns the populations of that area. If you cache a result with `load_or_compute`, put the area in its name, for example `f"rate_bars_{area}"`.
- Read data only through `simulation` (`simulation.backend.get_spike_events(...)`, `simulation.network.config`, `simulation.simulation_config`) so the analysis also works on saved runs.
- Many simulations with one parameter changed (a sweep, an f-I curve) are not an analysis of one run. Write them as a script under `experiments/` (see [Experiments](#experiments)).
- A package that provides analyses can register them too, by listing the module under the `microcircuit_lab.analyses` entry-point group in its `pyproject.toml` (see `microcircuit_lab/analysis/registry.py`).

## Testing

```bash
pytest
```

The scientific transformation functions and configuration preprocessing are tested independently from simulator execution where possible.

The tests cover the core: how config files are read and validated, the transformations, the analysis and the simulator backend. They do not test a builder itself. What a builder writes is tested by the core reading it, for example by validating every network config under `configs/network/`. A test for your own builder goes in `tests/` like any other.
