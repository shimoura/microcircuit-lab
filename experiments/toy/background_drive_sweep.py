"""How much external drive does the toy network need to actually spike?

An example experiment: a small parameter sweep over one population
parameter (background_indegree), using the public Simulation/analysis
API directly -- no new abstraction beyond what microcircuit_lab already
provides. This is the same question (and the same answer, K_ext=1000)
that calibrated configs/network/toy/populations.yaml in the first place;
see the toy network's own comments for how that value was chosen.

Run from the repository root:

    python experiments/toy/background_drive_sweep.py
"""

from __future__ import annotations

import matplotlib.pyplot as plt

from microcircuit_lab.analysis import compute_population_firing_rates
from microcircuit_lab import Simulation, prepare_network, read_network
from microcircuit_lab.config.simulation import SimulationConfig

BACKGROUND_INDEGREES = [200, 500, 1000, 2000, 4000]
OUTPUT_DIR = "output/experiments/toy_background_drive_sweep"


def run_one(background_indegree: float) -> dict[str, float]:
    network = read_network("configs/network/toy")
    populations = {
        name: population.model_copy(update={"background_indegree": background_indegree})
        for name, population in network.populations.items()
    }
    network = prepare_network(network.model_copy(update={"populations": populations}))

    simulation_config = SimulationConfig.model_validate(
        {
            "t_sim": 1000.0,
            "local_num_threads": 4,
            "print_time": False,
            "output": {
                "output_dir": f"{OUTPUT_DIR}/k_ext_{int(background_indegree)}",
                "overwrite": True,
            },
        }
    )

    simulation = Simulation(
        network=network,
        simulation_config=simulation_config,
        network_name="toy",
        simulation_name=f"k_ext_{int(background_indegree)}",
    )
    simulation.run()

    return compute_population_firing_rates(simulation)


def main() -> None:
    results = [
        {"background_indegree": k_ext, **run_one(k_ext)} for k_ext in BACKGROUND_INDEGREES
    ]

    pop_names = [name for name in results[0] if name != "background_indegree"]

    print(f"\n{'K_ext':>8}  " + "  ".join(f"{name:>10}" for name in pop_names))
    for row in results:
        rates = "  ".join(f"{row[name]:>10.2f}" for name in pop_names)
        print(f"{row['background_indegree']:>8}  {rates}")

    fig, ax = plt.subplots(figsize=(5, 3.5), dpi=150)
    for name in pop_names:
        ax.plot(
            [row["background_indegree"] for row in results],
            [row[name] for row in results],
            marker="o",
            label=name,
        )
    ax.set_xlabel("Background indegree (K_ext)")
    ax.set_ylabel("Mean firing rate (spikes/s)")
    ax.legend(frameon=False)
    fig.tight_layout()

    plot_path = f"{OUTPUT_DIR}/rate_vs_background_indegree.png"
    fig.savefig(plot_path, dpi=150, bbox_inches="tight")
    print(f"\nSaved comparison plot: {plot_path}")


if __name__ == "__main__":
    main()
