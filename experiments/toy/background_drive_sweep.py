"""How much external drive does the toy network need to actually spike?

An example experiment: a small parameter sweep over one population
parameter (the indegree in poisson_background.yaml), using the public Simulation/analysis
API directly -- no new abstraction beyond what microcircuit_lab already
provides. This is the same question (and the same answer, K_ext=1000)
that calibrated configs/network/toy/poisson_background.yaml in the first place;
see the toy network's own comments for how that value was chosen.

Run from the repository root:

    python experiments/toy/background_drive_sweep.py
"""

from __future__ import annotations

import matplotlib.pyplot as plt

from microcircuit_lab import Simulation, read_network, read_run
from microcircuit_lab.analysis import compute_population_firing_rates
from microcircuit_lab.config.simulation import SimulationConfig

BACKGROUND_INDEGREES = [200, 500, 1000, 2000, 4000]
OUTPUT_DIR = "output/experiments/toy_background_drive_sweep"


def run_one(indegree: float) -> dict[str, float]:
    network = read_network("configs/network/toy")
    poisson_background = {
        name: entry.model_copy(update={"indegree": indegree})
        for name, entry in network.poisson_background.items()
    }
    network = network.model_copy(update={"poisson_background": poisson_background})

    simulation_config = SimulationConfig.model_validate(
        {
            "t_sim": 1000.0,
            "local_num_threads": 4,
            "print_time": False,
            "output": {
                "output_dir": f"{OUTPUT_DIR}/k_ext_{int(indegree)}",
                "overwrite": True,
            },
        }
    )

    simulation = Simulation(
        network=network,
        simulation_config=simulation_config,
        network_name="toy",
        simulation_name=f"k_ext_{int(indegree)}",
    )
    simulation.run()

    return compute_population_firing_rates(read_run(simulation.output_dir))


def main() -> None:
    results = [
        {"indegree": k_ext, **run_one(k_ext)} for k_ext in BACKGROUND_INDEGREES
    ]

    pop_names = [name for name in results[0] if name != "indegree"]

    print(f"\n{'K_ext':>8}  " + "  ".join(f"{name:>10}" for name in pop_names))
    for row in results:
        rates = "  ".join(f"{row[name]:>10.2f}" for name in pop_names)
        print(f"{row['indegree']:>8}  {rates}")

    fig, ax = plt.subplots(figsize=(5, 3.5), dpi=150)
    for name in pop_names:
        ax.plot(
            [row["indegree"] for row in results],
            [row[name] for row in results],
            marker="o",
            label=name,
        )
    ax.set_xlabel("Background indegree (K_ext)")
    ax.set_ylabel("Mean firing rate (spikes/s)")
    ax.legend(frameon=False)
    fig.tight_layout()

    plot_path = f"{OUTPUT_DIR}/rate_vs_indegree.png"
    fig.savefig(plot_path, dpi=150, bbox_inches="tight")
    print(f"\nSaved comparison plot: {plot_path}")


if __name__ == "__main__":
    main()
