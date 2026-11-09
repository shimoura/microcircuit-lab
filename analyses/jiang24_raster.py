"""The raster plot of Jiang et al. (2024), Fig. 6A, with the axes of the publication.

The axes follow ``plotraster`` in ``plots.py`` of the official code: every neuron
has a row, the first population is at the top, and the y axis names the layers.
The analysis file gives the time window and switches the plot on::

    jiang24_raster: {enabled: true, begin: 10000.0, end: 10200.0}
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from microcircuit_lab.analysis import register_plot
from microcircuit_lab.analysis.plot_styles import population_color, population_metadata

LAYER_LABELS = {"L23": "L2/3", "L4": "L4", "L5": "L5", "L6": "L6"}
CELL_TYPE_LABELS = {"E": "Exc", "PV": "PV", "SOM": "SOM", "VIP": "VIP"}


def plot_jiang24_raster(run, config, style, save_path):
    fig, ax = plt.subplots(figsize=(2, 1.5), dpi=style.dpi)

    first_row = 0
    layer_rows: dict[str, list[int]] = {}
    for index, population in enumerate(run.populations):
        nodes = run.node_ids(population)
        senders, times = run.spikes(population)
        in_window = (times >= config["begin"]) & (times < config["end"])
        ax.scatter(
            times[in_window],
            first_row + np.searchsorted(nodes, senders[in_window]),
            marker=".",
            s=5,
            lw=0,
            color=population_color(population, index, style),
        )
        layer = population_metadata(population)[1]
        layer_rows.setdefault(layer, []).extend([first_row, first_row + len(nodes) - 1])
        first_row += len(nodes)

    for cell_type, label in CELL_TYPE_LABELS.items():
        ax.scatter([], [], s=4, label=label, color=style.cell_type_colors[cell_type])
    ax.legend(loc="upper center", ncol=4, bbox_to_anchor=(0.5, 1.2), fontsize=5, frameon=False)

    ax.invert_yaxis()
    ax.set_yticks(
        [(rows[0] + rows[-1]) / 2 for rows in layer_rows.values()],
        [LAYER_LABELS[layer] for layer in layer_rows],
        rotation=10,
    )
    ax.set_xticks(np.linspace(config["begin"], config["end"], 3))
    ax.tick_params(labelsize="xx-small")
    ax.set_xlabel("Time (ms)", fontsize="xx-small", labelpad=1.0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_position([0.15, 0.22, 0.8, 0.6])
    fig.savefig(save_path)


register_plot("jiang24_raster", plot_jiang24_raster)
