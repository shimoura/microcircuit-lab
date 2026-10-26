# Contributing

First ask whether the change belongs in the core. Behaviour that only your project needs goes in your project's `builders/` or `analyses/`, which the core finds without edits. Change the core when the fix or feature would help any project.

1. Fork the repository on GitHub and clone your fork.
2. Install it editable: `pip install -e ".[dev]"`. Tests that run a simulation need NEST, and the Brian2 tests need `.[brian2]` (they are skipped without it); see the installation section of [microcircuit_lab/README.md](microcircuit_lab/README.md#installation) for the ways to get it.
3. Create a branch, make the change and add a test for it.
4. Run `ruff check .` and `pytest`. CI runs both.
5. Push the branch to your fork and open a pull request into `main`.

A project made with `init --with-core` has a copy of the core with only the backends of the simulators installed when it was made; `init <project> --with-core --backends <name>` adds another.

To pull later changes into your fork, add this repository as a remote: `git remote add upstream git@github.com:shimoura/microcircuit-lab.git`.

## Changing the core

### Follow the name

A concept keeps its name from the YAML file to the test. To change something, start from its YAML file and follow the name:

```mermaid
%%{init: {"flowchart": {"wrappingWidth": 400}}}%%
flowchart TD
  Y["configs/network/toy_stimulated/stimuli.yaml"] --> C["config/stimuli.py<br/>what the file may contain"]
  C --> B["backends/nest/simulator.py<br/>create_stimuli: builds it in NEST"]
  B --> T["tests/test_stimuli.py"]
```

The files hold the numbers that are simulated; the simulator only turns each background rate per synapse into the rate of its generator (rate × indegree, `generator_rate` in `config/poisson_background.py`). Scaling and constant currents are builder steps (`builder_tools/`). The code behind each step from a builder to the plots: [docs/workflow.md](docs/workflow.md).

### Does your idea fit what already exists?

```mermaid
flowchart TD
  Q{"One more of something<br/>the files already have?<br/>(a stimulus type, a plot, ...)"}
  Q -->|yes| T["Find its recipe below:<br/>2–3 files, a test, docs,<br/>then a pull request"]
  Q -->|"no, a new concept<br/>(spatial structure, plasticity)"| D["Open an issue with<br/>a short design note first"]
  D --> S["Small pull requests,<br/>one step each, with<br/>a small example network"]
```

A new concept touches every step and raises scientific questions to answer before the code. For spatial structure, for example: does `N_scaling` keep the density or the size of the sheet, and what does `K_scaling` do to a connection kernel? The design note settles those, so each pull request can be reviewed on its own.

### Recipes

Click the kind of change. Each recipe ends with a test and a line in the README. A change in `config/` also needs `python docs/write_config_files.py`, which rewrites [docs/config_files.md](docs/config_files.md); a test fails until you do.

<details>
<summary><b>A stimulus type</b></summary>

1. `config/stimuli.py`: add a class next to the others, and add it to `StimulusConfig` at the end of the file.
2. `backends/nest/simulator.py`, `create_stimuli`: create its NEST device. Change `connect_stimuli` only if it connects differently.
   `backends/brian2/inputs.py`: its rate or current over time in `_stimulus_curve` (or its own Brian2 objects in `create_stimuli`).
3. Test in `tests/test_stimuli.py`.

The [worked example](#an-example-a-single-spike-stimulus) below does exactly this.
</details>

<details>
<summary><b>A weight or delay distribution</b></summary>

A distribution only one project needs doesn't go in the core: with Brian2 it is a `Distribution` in the project's `extensions/brian2/` (see "Distributions of your own" in the core's README). A shared one, which every simulator draws:

1. `config/connectivity.py`: add its name to `SHARED_DISTRIBUTIONS`.
2. `backends/nest/distributions.py`: draw it in `create_weight_spec` or `create_delay_parameter`.
   `backends/brian2/distributions.py`: its Brian2 expression in `DRAWS`, and its chance of crossing a bound in `chance_below`.
3. Test in `tests/test_bound_mode_and_tau_syn.py`.
</details>

<details>
<summary><b>A field on a population</b></summary>

1. `config/populations.py`: add it to `PopulationEntry` (the file) and `PopulationConfig` (the network).
2. `network/load.py`, `assemble_network`: copy it from one to the other.
3. `backends/nest/simulator.py`: use it in `create_populations` or `initialize_population`; `backends/brian2/simulator.py`: in `create_populations`.
4. Test in `tests/test_config_validation.py`.
</details>

<details>
<summary><b>A field on a connection, or a connection rule</b></summary>

A rule only one project needs doesn't go in the core: with Brian2 it is a `ConnectionRule` in the project's `extensions/brian2/` (see "Connection rules of your own" in the core's README). A shared rule, one that every simulator runs:

1. `config/connectivity.py`: add it to `ConnectionConfig` (a field), or to `SHARED_RULES` (a rule; to `RULE_NUMBER` too if it takes a number).
2. `config/connection_table.py`: add a field's column to `COLUMNS` (the core holds all connections as one table; it refuses to load until the new field has a column).
3. `backends/nest/simulator.py`: use it in `create_connections`, which reads the table column by column; `backends/brian2/simulator.py` too, and a rule in `backends/brian2/connections.py`: its counts in `_counts` if it takes a number, its `connect` call in `_single`.
4. If scaling or the indegrees depend on it: `builder_tools/mean_input.py` (`expected_synapses`) and `builder_tools/scaling.py` (`_check_connections_can_scale` for a rule that can't follow the scaling), on whole columns.
5. Test in `tests/test_connection_rules.py`.
</details>

<details>
<summary><b>A scaling or compensation option</b></summary>

1. `builder_tools/scaling.py`: the option, as an argument of `scale_network`, and its formula.
2. The same option in the `parameters` of the record it writes (`ScalingRecord`, `config/scaling.py`, is `scaling.yaml`).
3. `builder_tools/constant_current.py`, for a compensation current.
4. Test in `tests/test_scaling.py` or `tests/test_scaling_compensation.py`, and in `tests/test_heterogeneous_areas.py` if it depends on cell types.
</details>

<details>
<summary><b>Something to record</b></summary>

1. `config/simulation.py`: add it to `RecordingConfig`.
2. `backends/nest/simulator.py`: a `create_*`/`connect_*` pair, and reading it back; `backends/brian2/recording.py`: a Brian2 monitor in a `create_*` function, and writing it in `save_recordings`.
3. `run_folder/write.py`, if it is saved in the run folder, and `run_folder/read.py` if `read_run` should give it.
4. Test in `tests/test_run_folder.py`.
</details>

<details>
<summary><b>A bundled plot</b></summary>

1. `analysis/<plot>.py`: the plot function `plot_<name>(run, ...)`, whose first parameter is the `Run` that `read_run` gives, a settings class, and `register_plot(...)` at the end.
2. `analysis/__init__.py`: import the module, so the plot is registered when the package loads.
3. Test in `tests/test_<plot>.py`.
</details>

<details>
<summary><b>A simulator</b></summary>

A new package `backends/<name>/` and a line in `get_backend`, `read_saved_spikes` and `read_saved_variable`; see "Adding a backend" in the README.
</details>

**No change to the core** is needed for a neuron model (name it in `neurons.yaml`, NESTML models too; for Brian2, define it in `extensions/brian2/`, see "Running with Brian2" in the README), for a connection rule, distribution or synapse model only one project needs (for Brian2, in `extensions/brian2/`; see "Names the simulator looks up" under "Configuration" in the README), or for a new network (a network folder or a builder; see "Adding a new network" in the README).

When a stimulus `type` is not known, the error message points to this section.

### An example: a single-spike stimulus

1. Write the config you want, e.g. in `stimuli.yaml`:
   ```yaml
   stimuli:
     - type: spike
       targets: [L4_E]
       spike_times: [500.0]
       weight: {mean: 87.8, rel_std: 0.0, unit: pA}
       delay: {mean: 1.5, rel_std: 0.0}
   ```
2. Running it fails with `stimuli.yaml: stimuli.0: Input tag 'spike' ... does not match any of the expected tags` and points here.
3. In `config/stimuli.py`, add the class next to the others and to `StimulusConfig`:
   ```python
   class SpikeStimulusConfig(StimulusBase):
       """Spikes at fixed times, e.g. a single-spike perturbation."""

       type: Literal["spike"] = "spike"
       spike_times: list[float] = Field(min_length=1, description="ms")
       weight: WeightDistribution
       delay: DelayDistribution
       synapse: str | None = Field(
           default=None,
           examples=["depressing"],
           description="name of an entry in synapses.yaml; omit for the default synapse",
       )
   ```
4. In `NestBackend.create_stimuli`, create its device:
   ```python
   elif isinstance(stimulus, SpikeStimulusConfig):
       model = "spike_generator"
       params["spike_times"] = stimulus.spike_times
   ```
   Connecting it needs nothing new: every stimulus except `dc` connects with its own weight, delay and synapse, like `poisson`.
5. A test in `tests/test_stimuli.py`, and the new type in the README's list of stimuli.

## Code style

- Use plain names close to the papers and reference codes (`N_scaling`, `K_ext`, `tau_syn_ex`), no extra layers, no logic written twice.
- Use pydantic models for anything read from a file, so a mistake is reported with the file and the field. A field's limits go in `Field(...)`, not in separate checks, together with a `description` (with its unit) and, for a required field, `examples=[...]`: [docs/config_files.md](docs/config_files.md) is written from them.
- Docstrings explain what the code does and why. Functions meant to be called from outside the core (the top-level API, `builder_tools`, `Simulation`, `analysis`, `run_folder.write.register_artifact`, `config.yaml_files`) use the NumPy docstring style (`Parameters`, `Returns`, `Raises`); internal ones can stay in prose. Comments are full lines above the code, never at the end of a line.
- Core tests check the core and how it reads a builder's output. They must not depend on a specific builder.
- Keep the field names of the config models stable (`populations`, `size`, `indegree`, ...): every run saves its network in `config.yaml` with those names, and renaming one breaks re-plotting old runs. A new field needs a default for the same reason. Rename a field only when its old name is wrong or misleading. The old name then fails with a message giving the new one (no conversion is kept), and the rename is listed in the release notes. Command-line flags, backend options and folder names follow the same rule but matter less, because they don't end up in a run folder.
