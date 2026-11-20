# Examples

Each folder here is one model, laid out like a project (`builders/`, `configs/`, `extensions/`, ...), with a README that gives its sources and how to run it.

| Example | Networks | Neurons | What it is |
| :--- | :--- | ---: | :--- |
| [toy](toy/README.md) | `toy`, `toy_from_builder`, `toy_stimulated` | 1,000 | two populations (E and I); the smallest example, written by hand with comments, and by a builder |
| [toy_two_areas](toy_two_areas/README.md) | `toy_two_areas`, `..._advanced`, `..._clustered` | 1,710 | a made-up two-area network with different layers and cell types (E, PV, SOM, VIP), and variants with the optional features on |
| [pd14](pd14/README.md) | `pd14`, `pd14_downscaled` | 77,169 | the Potjans & Diesmann (2014) microcircuit, and a copy scaled down to 10 % |
| [jiang24](jiang24/README.md) | `jiang24`, `jiang24_stp` | 6,448 | the Jiang et al. (2024) microcircuit of mouse somatosensory cortex, with PV, SOM and VIP interneurons, without and with short-term plasticity |
| [humam](humam/README.md) | `humam_single`, `humam_all` | 56 / 13,874 | the human multi-area model (Pronold et al. 2024): one area, or all 34, scaled down |

The neurons are those of the bundled network folders. `pd14` needs about 15 GB of memory; for a quick look, run `pd14_downscaled`.

## Running one

From the repository:

```bash title="Terminal"
cd examples/pd14
microcircuit-lab run --network pd14_downscaled
```

Or in your own project, where the example's files become yours:

```bash title="Terminal"
microcircuit-lab init my_project --example pd14
cd my_project
microcircuit-lab run --network pd14_downscaled
```

## Adding yours

A new model is a folder like these: a builder, its network models and a README with the model's sources. See [A new network model](../docs/new-network.md).
