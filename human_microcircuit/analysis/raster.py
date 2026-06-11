from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np


def plot_population_raster(
    simulation,
    figsize=(10, 8),
    markersize=0.5,
):
    """
    Plot a PD14-style raster with one horizontal block
    per population.
    """

    fig, ax = plt.subplots(figsize=figsize)

    populations = list(
        simulation.network.config.populations.keys()
    )

    y_offset = 0

    yticks = []
    ylabels = []

    for pop_name in populations:

        events = simulation.backend.get_spike_events(pop_name)

        senders = np.asarray(events["senders"])
        times = np.asarray(events["times"])

        #
        # convert to local ids
        #

        unique = np.unique(senders)

        mapping = {
            gid: i
            for i, gid in enumerate(unique)
        }

        y = np.array(
            [
                mapping[g]
                for g in senders
            ]
        )

        y = y + y_offset

        ax.scatter(
            times,
            y,
            s=markersize,
            rasterized=True,
        )

        yticks.append(
            y_offset + len(unique) / 2
        )

        ylabels.append(pop_name)

        y_offset += len(unique)

    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Population")

    ax.set_yticks(yticks)
    ax.set_yticklabels(ylabels)

    plt.tight_layout()

    plt.show()