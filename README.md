# Microcircuit Lab

Microcircuit Lab is a configuration-driven framework for building, simulating, and analyzing recurrent neural microcircuit models. It separates **model-specific data**, **generic network representation**, and **simulator backends** so published models can share the same simulation infrastructure.

## Contents

- [Using this as a template for a new project](#using-this-as-a-template-for-a-new-project)
- [Architecture](#architecture)
- [Project structure](#project-structure)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Adding a new model](#adding-a-new-model)
- [Adding a backend](#adding-a-backend)
- [Using a NESTML model](#using-a-nestml-model)
- [Included models](#included-models)
- [Experiments](#experiments)
- [Repository scripts](#repository-scripts)
- [Run outputs](#run-outputs)
- [Testing](#testing)

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

The fastest way to see the framework run is the bundled `toy` network, a minimal two-population (E/I) example under `configs/network/toy/`:

```python
from microcircuit_lab import Simulation

simulation = Simulation.from_yaml()  # defaults to network_name="toy", simulation_name="toy"
simulation.run()
```

Or run a published reference model the same way:

```python
from microcircuit_lab import Simulation

simulation = Simulation.from_yaml(network_name="pd14")
simulation.run()
```

Use `scripts/run_simulation.py` as the editable generic runner for any pre-generated network (defaults to `pd14`; pass `--network toy` for the minimal example -- `--simulation`/`--analysis` default to whatever `--network` is set to, see [Configuration](#configuration)). It can produce raster, firing-rate, power-spectrum, and ISI-CV diagnostics with one shared plot style. Use `scripts/generate.py <model>` to (re)generate a model's network configuration.

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

A network configuration describes biology and connectivity. A simulation configuration describes execution settings such as duration, seed, threads, and recording. An analysis configuration (`AnalysisConfig`, `microcircuit_lab/config/analysis.py`) describes presentation only -- which diagnostic plots run, the time window/area to analyze, and their styling (colors, figure sizes, raster neuron subsampling, ...); it has no effect on the simulation itself. These are three independent trees, matched by name, so one network can be paired with more than one execution profile or presentation (e.g. a short simulation for a quick check vs. a long one for a real run; a quick raster-only look vs. a full styled figure set for a paper) -- but in the common case where a network only ever has one of each, `Simulation.from_yaml(network_name=...)` and `AnalysisConfig.from_yaml(network_name=...)` alone are enough: `simulation_name`/`analysis_name` both default to whatever `network_name` is, so `configs/network/toy/` pairs automatically with `configs/simulation/toy.yaml` and `configs/analysis/toy.yaml`. Pass `simulation_name`/`analysis_name` explicitly only when you actually want a different, decoupled profile.

Unlike network/simulation configs, an analysis config is optional: if `configs/analysis/<name>.yaml` doesn't exist, `AnalysisConfig.from_yaml` falls back to built-in defaults rather than raising, so adding a new network never requires an analysis file. And because `AnalysisConfig`/`PlotStyle`/`RasterPlotConfig`/etc. are just pydantic models, a one-off tweak for a specific script or notebook doesn't need a YAML file at all -- override in memory instead, e.g. `plot_raster(sim, config=RasterPlotConfig(neuron_fraction=0.05))`. Save a variant to YAML only once it's a default you want to keep reusing; see [Experiments](#experiments) for where a one-off analysis script belongs instead.

Beyond `begin`/`end`/`area`/`show_reference`/`style`, `AnalysisConfig` doesn't pre-declare a field per plot -- `raster:`/`firing_rates:`/`power_spectrum:`/`isi_cv:` are just the top-level sections the four bundled diagnostics happen to be registered under (see [Adding a new diagnostic](#adding-a-new-diagnostic)). A section name that isn't registered raises a clear error rather than being silently ignored.

**Background input vs. stimulation.** `background_inputs.yaml` is the always-on background Poisson drive tied to `background_indegree`; it scales with `K_scaling` and is what the DC-compensation math in `network/scaling.py` accounts for. `stimuli.yaml` (optional -- omit both the file and the `stimuli:` entry in `network.yaml` if unused) describes targeted, time-limited devices for experiments instead: a constant-current pulse (`type: dc`), a Poisson train active for part of the run (`type: poisson`), or a piecewise-constant Poisson rate profile (`type: inhomogeneous_poisson`). Stimuli are not touched by scaling or compensation -- they're applied exactly as configured. See `StimulusConfig` in `microcircuit_lab/config/network.py` for the full field reference, e.g.:

**Poisson vs. DC background.** Add a top-level `background_mode: dc` to `background_inputs.yaml` (default is `poisson`) to replace the background Poisson generator network-wide with a constant current of equal mean, reproducing Potjans & Diesmann (2014)'s comparison of the two drive types (their Fig. 5) -- see `configs/network/pd14_dc/` for a ready-to-run example (`--network pd14_dc`, pairs with `configs/simulation/pd14_dc.yaml`) and `NetworkConfig.background_mode` / `NetworkPreprocessor._apply_background_dc_current` for the implementation.

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

**Weight units.** Every `weight` block requires a `unit` (see `WeightDistribution` in `microcircuit_lab/config/network.py`) -- deliberately no default, so a config can't silently run with the wrong conversion just because a field was left out. `PSP` (biological amplitude, mV) is converted to a current amplitude by `NetworkPreprocessor`, and that conversion (`network/synapses.py`) only depends on the target neuron having `C_m`, `tau_m`, `tau_syn_ex` and `tau_syn_in` parameters, not on the model's name; it applies to any current-based LIF neuron with single-exponential synaptic currents, `iaf_psc_exp` is just the model most people know it from. This module has no notion of "simulator" or "backend", so it can't check the model's actual dynamics for you: giving `unit: PSP` to a neuron that happens to have those four parameter names without actually having this dynamics will silently produce the wrong weight, so that's on whoever writes the config, the same way `unit: PSC`/`unit: native` already are explicit choices. For a genuinely different model (a conductance-based one, an adaptive-exponential one, or anything else), give its connections `unit: PSC` (if the weights are already current amplitudes in pA) or `unit: native` (used exactly as given, no interpretation at all) instead of `PSP`. Adding a new neuron model should essentially never require touching `network/parameters.py`.

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

**Formatting convention**: hand-edited files (e.g. `configs/network/toy/`) use normal YAML block style, one field per line, for readability. Generator-written tables that can run to thousands of uniform rows (`connectivity.yaml`, and `populations.yaml`/`background_inputs.yaml` for multi-area networks) are written one-record-per-line instead -- e.g. `humam_all`'s `connectivity.yaml` is ~8,400 lines of `- {source: ..., target: ..., weight: {...}, delay: {...}}` rather than ~100,000 lines of block style, with identical parsed content. Both styles are plain YAML and load identically; use `microcircuit_lab.io.files.write_yaml`/`flow_records` in a generator to opt a field into the compact style.

## Adding a new model

There are two supported ways to try a new model, and the core package (`network/`, `simulation/`, `config/`, `io/`, `backends/`) never has to change for either one.

**Write YAML directly.** Copy `configs/network/toy/` (the smallest complete example of the schema: two populations, four connections, minimal scaling/reference) to `configs/network/<my_model>/` and edit the values by hand. Pair it with a `configs/simulation/<my_model>.yaml` (every field has a default, so an empty file is valid). This is the right starting point for exploring a new idea or a model small enough to write out directly.

**Add a generator.** For models whose parameters come from source data (published tables, experimental recordings, pickled matrices, etc.), create `microcircuit_lab/models/<model_name>/` and keep all source-format assumptions there. The generator's job is to translate that data into the same YAML schema used above and write it under `configs/network/<model_name>/`. Follow `humam/generator.py` (full translation pipeline from bundled source data) or `pd14/generator.py` (a single derived file, rest static) depending on how much of the config is actually derived versus fixed.

If generation should be runnable from the command line, add an `add_cli(subparser)` function to the model's `generator.py` (same pattern in both examples above) and register it in `microcircuit_lab/models/__init__.py`'s `MODEL_GENERATORS`. It then becomes available as `python scripts/generate.py <model_name>` without any changes to `scripts/generate.py` itself.

Either way, once the generic configuration exists, run it through the same public API:

```python
from microcircuit_lab import Simulation

simulation = Simulation.from_yaml(network_name="my_model")
simulation.run()
```

Do not add model-specific branches to `network/`, `simulation/`, or a simulator backend unless the feature is genuinely generic.

## Adding a backend

Implement the small backend contract in `microcircuit_lab/backends/base.py`, place the implementation under `backends/<name>/`, and register it in `backends.get_backend`. Then select it with:

```python
simulation = Simulation.from_yaml(
    network_name="my_model",
    backend="nest",
)
```

`prepare_output(run_dir)` and `save_recordings(run_dir)` are where recording-to-disk should be implemented in whatever way is native and efficient for that simulator (see "Run outputs" below); `get_spike_events()` should transparently read that data back regardless of how it was stored, so callers (analysis, `io/output.py`) never need backend-specific branches.

A backend's constructor isn't limited to `(network, simulation_config)`: it can accept additional keyword-only arguments for whatever it alone needs, passed through `Simulation.from_yaml(..., backend_options={...})` without `Simulation`/`config`/`network` ever inspecting them (see `SimulationBackend` in `backends/base.py`). `NestBackend`'s `extension_modules` is the current example; see [Using a NESTML model](#using-a-nestml-model) for it in context.

## Using a NESTML model

NESTML compiles a custom neuron model into a NEST extension module, loaded at runtime with `nest.Install(module_name)` before any node using that model can be created. This is entirely a capability of `NestBackend` (its `extension_modules` constructor argument, see "Adding a backend" above); nothing elsewhere in the package has any notion of NESTML.

**Where files go.** Keep `.nestml` source under a top-level `nestml/` directory (parallel to `configs/`, not inside `microcircuit_lab/models/`: nothing reads a `.nestml` file at runtime, NESTML's own compiler does, and a compiled module is platform/NEST-version-specific, not something to ship as package data). A model reusable across networks can sit flat; one written specifically for a given model follows the same `<model_name>/` subdirectory convention already used by `configs/network/<model>/` and `experiments/<model>/`. Compiled output is gitignored, like `output/`:

```text
nestml/
├── generic_lif.nestml           # reusable across networks
└── humam/
    └── humam_lif.nestml         # written specifically for the HuMAM reproduction
```

Compile it with NESTML's own tooling, once, ahead of time (same idea for a model-specific one under `nestml/<model_name>/`, just with that path instead):

```python
from pynestml.frontend.pynestml_frontend import generate_nest_target

generate_nest_target(
    input_path="nestml/generic_lif.nestml",
    target_path="nestml/build/my_module",
    module_name="my_module",
)
```

This registers the model under whatever name your `.nestml` file (or NESTML's default suffixing) gives it, e.g. `generic_lif_nestml`. From there it's just another neuron model as far as `neurons.yaml` is concerned: use that name as `model`, its own parameters as `parameters`, and `psp_conversion_aliases` if you're using `unit: PSP` and it names things differently (see [Configuration](#configuration)).

Test a NESTML neuron against a network you already trust by copying it rather than editing in place, e.g. `configs/network/toy/` to `configs/network/toy_nestml/`, the same way `toy_stimulated` was kept separate from `toy`.

The only NEST-specific step is telling `NestBackend` to load the compiled module before building the network:

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

Model-specific documentation is located inside each package under `microcircuit_lab/models/`.

## Experiments

An experiment -- a parameter sweep, a comparison across configs, exploratory analysis for a specific model -- is a plain Python script under `experiments/<model_name>/<experiment_name>.py`. There's no dedicated framework for this beyond `Simulation`/`microcircuit_lab.analysis`: build a network config (from YAML, or with fields overridden in-memory as needed), run it, and use the same `compute_*`/`plot_*` functions as everywhere else. See `experiments/toy/background_drive_sweep.py` for a worked example (a small sweep over one population parameter, reproducing how the toy network's own background drive was calibrated).

## Repository scripts

Model generation and simulation execution are intentionally separate: `scripts/generate.py` produces a model's config files, and `scripts/run_simulation.py` runs any pre-generated config by name -- or re-plots an existing run's recordings without re-simulating, via `--run-dir` (see below). Neither script contains model-specific logic, so both stay unchanged as models are added.

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

Use `--network` (or `--run-dir`, see below), `--simulation`, `--analysis`, `--area`, `--begin`, `--end`, `--reference`/`--no-reference`, and one `--<plot-name>`/`--no-<plot-name>` pair per entry in `microcircuit_lab.analysis.PLOT_REGISTRY` (`--raster`/`--no-raster`, `--firing-rates`/`--no-firing-rates`, `--power-spectrum`/`--no-power-spectrum`, `--isi-cv`/`--no-isi-cv` for the four bundled diagnostics -- see [Adding a new diagnostic](#adding-a-new-diagnostic) below for how a 5th one gets its own flag automatically) on `scripts/run_simulation.py` to select the network, simulation, analysis profile, analysis window, area, and which diagnostics run. Every one of these (except `--network`/`--run-dir`/`--simulation`/`--analysis` themselves) is an *optional override*: if omitted, the value comes from `configs/analysis/<analysis_name>.yaml` (see [Configuration](#configuration)) instead. Plots are saved to `<output_dir>/plots/` but not opened interactively by default; pass `--show` to also pop up the plot windows. Plot styling (colors, sizes, figure layout, raster neuron subsampling, spectral estimator, ...) is set entirely via that same analysis YAML, not hardcoded in the script.

### Re-plotting without re-simulating

A run already saves everything a plot needs (`config.yaml`, `recordings/`), so trying a different `--begin`/`--end`/`--area`/analysis profile on a run you already have doesn't require re-simulating it. Pass `--run-dir` instead of `--network`/`--simulation`; every other flag above works the same:

```bash
python scripts/run_simulation.py --network toy   # note the run_dir it prints
python scripts/run_simulation.py --run-dir output/toy/<timestamp> --begin 200 --end 400
```

Plots are written back into that same run's own `plots/` directory. Programmatically, this is `Simulation.from_run_dir(run_dir)` -- it returns a `Simulation` with a working `.backend` (reading spikes back from `recordings/` instead of a live NEST process, via `PostHocBackend`) without ever calling `.run()`, so `microcircuit_lab.analysis`'s `plot_*`/`compute_*` functions work on it exactly as they do on a freshly-run one. Only runs saved after this feature was added carry the `first_gid` metadata field it needs; an older run raises a clear error instead of silently reconstructing the wrong neuron IDs -- just re-run it once to pick up the new field.

### Adding a new diagnostic

Adding a 5th bundled plot (raster/firing-rates/power-spectrum/ISI-CV are the current four) doesn't touch `AnalysisConfig`, any `__init__.py` export list, or `scripts/run_simulation.py` -- it's a registry, the same pattern already used for simulator backends (`backends.get_backend`), model generators (`models.MODEL_GENERATORS`), and spectral estimators (`power_spectrum.POWER_SPECTRUM_METHODS`). Write the plot function (same shape as `plot_raster`/`plot_firing_rates`: `(simulation, begin, end, *, area, style, config, save_path, show)`) and a small config class for its own settings, then register it once:

```python
from microcircuit_lab.analysis import register_plot

register_plot(
    "spectrogram",
    config_cls=SpectrogramPlotConfig,
    plot_fn=plot_spectrogram,
    filename="spectrogram.png",
)
```

That's the entire wiring: `scripts/run_simulation.py` gets a `--spectrogram`/`--no-spectrogram` flag automatically (it builds its CLI by looping over `microcircuit_lab.analysis.PLOT_REGISTRY`), and `configs/analysis/*.yaml` files don't need to change shape at all -- a `spectrogram:` top-level section works exactly like `raster:`/`firing_rates:` already do (an unregistered section name raises a clear error instead of being silently ignored, via `check_unknown_plot_sections`). This works from your own code too, e.g. a module under `experiments/<model>/` -- calling `register_plot` there plugs a project-specific diagnostic into the same CLI/YAML dispatch without editing this package at all.

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
