from __future__ import annotations

import matplotlib.pyplot as plt


def plot_raster(events) -> None:
    """
    Plot a simple raster from native NEST events.
    """

    plt.figure(figsize=(10, 6))

    plt.scatter(
        events["times"],
        events["senders"],
        s=1,
    )

    plt.xlabel("Time (ms)")
    plt.ylabel("Neuron ID")

    plt.tight_layout()

    plt.show()