"""What a backend prints after simulating."""

from __future__ import annotations

import logging
from collections.abc import Callable


def log_firing_rates(
    logger: logging.Logger, spike_events: Callable[[str], dict], sizes: dict[str, int], t_sim: float
) -> None:
    """
    Log the number of spikes and the mean firing rate of each population.

    ``spike_events`` is the backend's ``get_spike_events``, ``sizes`` the
    number of neurons of each population and ``t_sim`` the simulated time (ms).
    """

    t_sim_s = t_sim / 1000.0
    for pop_name, n_neurons in sizes.items():
        n_spikes = len(spike_events(pop_name)["times"])
        mean_rate = (n_spikes / (n_neurons * t_sim_s)) if (n_neurons and t_sim_s > 0) else 0.0
        logger.info(
            "%-6s  N=%5d  spikes=%7d  rate=%8.3f Hz",
            pop_name,
            n_neurons,
            n_spikes,
            mean_rate,
        )
