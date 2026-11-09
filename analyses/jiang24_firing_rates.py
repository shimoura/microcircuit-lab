"""The firing rates of Jiang et al. (2024), Fig. 6A, next to the experimental data.

Follows ``plot_fr_median`` in ``plots.py`` of the official code. Each population
has a box of the rates of its neurons (quartiles and median, whiskers to the
lowest and highest rate) and a black box of the experimental quartiles. The
analysis file gives the time window and the experimental data, and switches the
plot on::

    jiang24_firing_rates:
      enabled: true
      begin: 10000.0
      end: 15000.0
      experiment: {L23_E: [0.5, 0.6, 4.5], ...}
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

from microcircuit_lab.analysis import compute_neuron_firing_rates, register_plot
from microcircuit_lab.analysis.plot_styles import population_color

BOX_WIDTH = 0.24
LINE_WIDTH = 0.5
Y_LIMITS = (-5.0, 115.0)
CELL_TYPE_LABELS = {"E": "Exc", "PV": "PV", "SOM": "SOM", "VIP": "VIP"}


def _box(ax, left, quartiles, color):
    """A box from the first to the third quartile, with a line at the median."""
    first, median, third = quartiles
    ax.add_patch(
        Rectangle((left, first), BOX_WIDTH, third - first, linewidth=LINE_WIDTH, edgecolor=color, facecolor="none")
    )
    ax.plot([left, left + BOX_WIDTH], [median, median], color=color, linewidth=LINE_WIDTH)


def _whisker(ax, center, start, stop, color):
    """A line from a box to the lowest or highest rate, with a cap at its end."""
    ax.plot([center, center], [start, stop], color=color, linewidth=LINE_WIDTH)
    cap = BOX_WIDTH / 4
    ax.plot([center - cap, center + cap], [stop, stop], color=color, linewidth=LINE_WIDTH)


def plot_jiang24_firing_rates(run, config, style, save_path):
    fig, ax = plt.subplots(figsize=(2, 1.5), dpi=style.dpi)
    rates = compute_neuron_firing_rates(run, config["begin"], config["end"])

    for x, (population, neuron_rates) in enumerate(rates.items()):
        color = population_color(population, x, style)
        quartiles = np.quantile(neuron_rates, [0.25, 0.5, 0.75])
        _box(ax, x - BOX_WIDTH, quartiles, color)
        _whisker(ax, x - BOX_WIDTH / 2, quartiles[2], neuron_rates.max(), color)
        _whisker(ax, x - BOX_WIDTH / 2, quartiles[0], neuron_rates.min(), color)
        _box(ax, x, config["experiment"][population], "k")

    ax.set_xlim(-0.5, 12.5)
    ax.set_ylim(Y_LIMITS)
    ax.set_xticks([])
    ax.set_yticks(np.arange(0.0, Y_LIMITS[1], 20.0))
    ax.tick_params(labelsize="xx-small")

    # L2/3 and L5 are shaded; each layer is named above the axes.
    height = Y_LIMITS[1] - Y_LIMITS[0]
    ax.add_patch(Rectangle((-0.5, Y_LIMITS[0]), 4.0, height, color="lightgray", zorder=0))
    ax.add_patch(Rectangle((6.5, Y_LIMITS[0]), 3.0, height, color="lightgray", zorder=0))
    for x, layer in ((1.5, "L2/3"), (5.0, "L4"), (8.0, "L5"), (11.0, "L6")):
        ax.text(x, Y_LIMITS[1] + 2, layer, ha="center", fontsize="xx-small")

    for cell_type, label in CELL_TYPE_LABELS.items():
        ax.scatter(
            [], [], marker="s", s=4, linewidth=0.6, label=label,
            facecolors="none", edgecolors=style.cell_type_colors[cell_type],
        )
    ax.scatter([], [], marker="s", s=4, linewidth=0.6, label="Exp", facecolors="none", edgecolors="k")
    ax.legend(loc="upper left", ncol=1, fontsize=4, frameon=False)

    ax.spines[["top", "right"]].set_visible(False)
    ax.set_ylabel("spikes/s", fontsize="x-small")
    ax.set_title("Neuronal firing rate", fontsize="x-small", pad=10)
    fig.tight_layout(pad=0.8)
    fig.savefig(save_path)


register_plot("jiang24_firing_rates", plot_jiang24_firing_rates)
