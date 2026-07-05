"""
Raster plot utilities.
"""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt


POPULATION_ORDER = [
    "L23_E",
    "L23_I",
    "L4_E",
    "L4_I",
    "L5_E",
    "L5_I",
    "L6_E",
    "L6_I",
]

COLORS = [
    "#595289",
    "#af143c",
] * 4


def plot_raster(
    simulation,
    begin: float = 0.0,
    end: float | None = None,
) -> None:
    """
    Plot a raster similar to the original PD14 implementation.

    Parameters
    ----------
    simulation
        Executed Simulation object.

    begin
        Start time (ms).

    end
        End time (ms). If None, uses the simulation duration.
    """

    if simulation.backend is None:
        raise RuntimeError(
            "Simulation has not been run yet."
        )

    if end is None:
        end = simulation.simulation_config.t_sim

    #
    # PD14 plotting style
    #

    fig_size = (4, 3)
    marker_size = 1
    alpha = 1.0

    plt.rcParams["figure.figsize"] = fig_size
    plt.rcParams["figure.dpi"] = 300

    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.size"] = 8

    plt.rcParams["axes.titlesize"] = 10
    plt.rcParams["axes.labelsize"] = 8

    plt.rcParams["xtick.labelsize"] = 8
    plt.rcParams["ytick.labelsize"] = 8

    plt.rcParams["ytick.major.size"] = 0

    plt.figure()
    plt.clf()

    #
    # highest gid
    #

    last_gid = max(
        simulation.backend.get_population("L6_I").tolist()
    )

    layer_positions = []
    layer_labels = ["L2/3", "L4", "L5", "L6"]

    for i, pop_name in enumerate(POPULATION_ORDER):

        events = simulation.backend.get_spike_events(pop_name)

        times = np.asarray(events["times"])
        senders = np.asarray(events["senders"])

        #
        # time window
        #

        mask = (times >= begin) & (times <= end)

        times = times[mask]
        senders = senders[mask]

        #
        # reverse ids exactly like PD14
        #

        neurons = np.abs(senders - last_gid) + 1

        #
        # plot
        #

        plt.plot(
            times,
            neurons,
            "o",
            ms=marker_size,
            alpha=alpha,
            color=COLORS[i],
            mew=0,
            rasterized=True,
        )

        #
        # layer separator
        #

        nodes = simulation.backend.get_population(pop_name)

        gids = np.asarray(nodes.tolist())

        mod_gids = np.abs(gids - last_gid) + 1

        if i % 2 == 0:
            plt.hlines(
                mod_gids[0],
                begin,
                end,
                color="0.8",
                ls="-",
                lw=1,
                zorder=0,
            )

        #
        # layer labels
        #

        if i % 2 == 0:

            next_nodes = simulation.backend.get_population(
                POPULATION_ORDER[i + 1]
            )

            next_gids = np.asarray(next_nodes.tolist())

            next_mod = np.abs(next_gids - last_gid) + 1

            layer_positions.append(
                0.5 * (mod_gids[0] + next_mod[-1])
            )

    plt.xlabel("time (ms)")
    plt.ylabel("neuron id")

    plt.yticks(
        layer_positions,
        layer_labels,
    )

    plt.xlim(begin, end)

    plt.tight_layout()

    plt.show()