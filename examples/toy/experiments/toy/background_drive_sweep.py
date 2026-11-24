"""How much background input does the toy network need to fire?

A sweep over the background indegree: each value becomes a network folder of
its own, a copy of the toy with that one number changed, run with the toy's
settings. The toy's 1000 inputs were chosen this way. Tutorial 5
(docs/tutorials/5_parameter_sweep.ipynb) runs the same loop in a notebook.

Run from the toy example's folder (examples/toy), or from a project that has it:

    python experiments/toy/background_drive_sweep.py
"""

import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import yaml

from microcircuit_lab import Simulation, read_network, read_run
from microcircuit_lab.analysis import compute_population_firing_rates
from microcircuit_lab.config.simulation import SimulationConfig

# The toy's settings, as a dict. Seven short runs need no progress line from NEST
# (in a notebook, it would hang the kernel).
settings = yaml.safe_load(Path("configs/simulation/toy.yaml").read_text())
settings["print_time"] = False

indegrees = [600, 700, 800, 900, 1000, 1100, 1200]
rates = {}
for indegree in indegrees:
    # Each value is a network folder of its own: a copy of the toy with another indegree.
    name = f"toy_indegree_{indegree}"
    folder = Path("configs/network") / name
    shutil.copytree("configs/network/toy", folder, dirs_exist_ok=True)
    background_file = folder / "poisson_background.yaml"
    background = yaml.safe_load(background_file.read_text())
    for entry in background["poisson_background"].values():
        entry["indegree"] = indegree
    background_file.write_text(yaml.safe_dump(background, sort_keys=False))

    simulation = Simulation(
        read_network(folder), SimulationConfig(**settings), network_name=name, simulation_name="toy"
    )
    simulation.run()
    rates[indegree] = compute_population_firing_rates(read_run(simulation.output_dir), begin=200.0)

for indegree, rate in rates.items():
    print(f"indegree {indegree:5d}:  E {rate['E']:5.1f}   I {rate['I']:5.1f}  spikes/s")

fig, ax = plt.subplots(figsize=(4, 3))
for population in ["E", "I"]:
    ax.plot(indegrees, [rates[k][population] for k in indegrees], "o-", label=population)
ax.set_xlabel("background indegree")
ax.set_ylabel("rate (spikes/s)")
ax.legend()
fig.tight_layout()
fig.savefig("output/background_sweep.png")
print("Saved output/background_sweep.png")
