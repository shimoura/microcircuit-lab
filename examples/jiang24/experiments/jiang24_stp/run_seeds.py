"""Run the jiang24_stp network with the seeds of the publication's 20 simulations.

From the project folder, after ``microcircuit-lab generate jiang24 --stp``::

    python experiments/jiang24_stp/run_seeds.py

Each seed gets its own run folder under ``output/jiang24_stp_seeds/seed_<seed>/``.
"""

from microcircuit_lab import Simulation

SEEDS = range(55, 75)

for seed in SEEDS:
    simulation = Simulation.from_yaml(network_name="jiang24_stp")
    settings = simulation.simulation_config
    output = settings.output.model_copy(update={"output_dir": f"output/jiang24_stp_seeds/seed_{seed}"})
    simulation.simulation_config = settings.model_copy(update={"rng_seed": seed, "print_time": False, "output": output})
    simulation.run()
