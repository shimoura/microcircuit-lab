# Running from a script (optional)

`microcircuit-lab run --network toy` is enough to run a network. A Python script helps when you run many: several seeds, a parameter sweep, any batch. The same run as the command, without the plots:

```python
from microcircuit_lab import Simulation

simulation = Simulation.from_yaml(network_name="toy")   # configs/network/toy + configs/simulation/toy.yaml
simulation.run()
print(simulation.output_dir)                            # output/toy/<timestamp>
```

Put scripts in your project's `experiments/` and run them from the project folder (`python experiments/seeds.py`), so `configs/` and `output/` are found.

## Change the settings

The simulation file, read as a plain dict, is the settings: change a value, then run.

```python
import yaml
from microcircuit_lab import Simulation, read_network
from microcircuit_lab.config.simulation import SimulationConfig

settings = yaml.safe_load(open("configs/simulation/toy.yaml"))   # {"t_sim": 1000.0, "rng_seed": 42, ...}
settings["t_sim"] = 2000.0
settings["rng_seed"] = 7

network = read_network("configs/network/toy")
Simulation(network, SimulationConfig(**settings), network_name="toy").run()
```

`SimulationConfig(**settings)` checks the values as the file would be checked.

## Several seeds

The same, in a loop. Give each group of runs its own output folder:

```python
for seed in [1, 2, 3]:
    settings["rng_seed"] = seed
    settings["output"]["output_dir"] = f"output/toy_seeds/seed_{seed}"
    Simulation(network, SimulationConfig(**settings), network_name="toy").run()
```

Each run gets its own `<timestamp>` folder in there, with its spikes and the settings it ran with.

## A sweep over the network model

To change the network model itself, write each variant as a network folder: copy the original, change a value in the YAML (a plain dict again), run. Every variant then stays a folder you can open and run again.

```python
import shutil
from pathlib import Path

import yaml
from microcircuit_lab import Simulation

for indegree in [800, 1000, 1200]:
    name = f"toy_indegree_{indegree}"
    folder = Path("configs/network") / name
    shutil.copytree("configs/network/toy", folder, dirs_exist_ok=True)

    background_file = folder / "poisson_background.yaml"
    background = yaml.safe_load(background_file.read_text())
    for entry in background["poisson_background"].values():
        entry["indegree"] = indegree
    background_file.write_text(yaml.safe_dump(background, sort_keys=False))

    Simulation.from_yaml(network_name=name, simulation_name="toy").run()
```

The rewritten file loses its comments; the others are copied as they are. [Tutorial 5](tutorials/5_parameter_sweep.ipynb) does this sweep and plots the result.

## Results

Every run is a folder; read it back with `read_run`, now or years later, without the simulator:

```python
from microcircuit_lab import read_run
from microcircuit_lab.analysis import compute_population_firing_rates, plot_raster

run = read_run("output/toy/<timestamp>")
compute_population_firing_rates(run, begin=200.0)                 # {"E": 20.3, "I": 20.8}, spikes/s
plot_raster(run, save_path=run.folder / "plots" / "raster.png", show=False)
```

More: [The run folder](run-folder.md), [Analysing a run](analysis.md).

## Good to know

- The runs of one script go one after another; the simulator starts afresh for each. For runs in parallel, start several scripts.
- With several MPI processes, save or plot only where `simulation.is_main_process` is true ([NEST](nest.md#several-mpi-processes-optional)).
- The settings also choose the simulator (`backend`): a run uses NEST unless the settings say otherwise.
- Every function, with its arguments: [Python API](api.md).
