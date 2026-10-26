# Two-area toy network

A small synthetic multi-area network (24 populations, about 1,700 neurons) that shows how a multi-area model is described, and tests that the core handles areas with different layers and cell types. The numbers are made up: it is a test case and an example, not a model of cortex.

```bash
microcircuit-lab run --network toy_two_areas     # plots for each area under plots/A and plots/B
microcircuit-lab generate toy_two_areas          # rewrite configs/network/toy_two_areas/ from data.py
microcircuit-lab run --network toy_two_areas_advanced   # the same network with optional features on (below)
microcircuit-lab run --network toy_two_areas_clustered  # the same network split into clusters (below)
```

## Areas and populations

```mermaid
%%{init: {"flowchart": {"nodeSpacing": 10, "rankSpacing": 12, "padding": 6, "wrappingWidth": 400}}}%%
flowchart LR
  subgraph A["Area A · 960 neurons"]
    direction TB
    subgraph A23[" "]
      direction LR
      a23l["L23"]:::layer ~~~ a23e["E 200"]:::E ~~~ a23p["PV 25"]:::PV ~~~ a23s["SOM 15"]:::SOM
    end
    subgraph A4[" "]
      direction LR
      a4l["L4"]:::layer ~~~ a4e["E 200"]:::E ~~~ a4p["PV 25"]:::PV ~~~ a4s["SOM 15"]:::SOM
    end
    subgraph A5[" "]
      direction LR
      a5l["L5"]:::layer ~~~ a5e["E 200"]:::E ~~~ a5p["PV 25"]:::PV ~~~ a5s["SOM 15"]:::SOM
    end
    subgraph A6[" "]
      direction LR
      a6l["L6"]:::layer ~~~ a6e["E 200"]:::E ~~~ a6p["PV 25"]:::PV ~~~ a6s["SOM 15"]:::SOM
    end
    A23 ~~~ A4 ~~~ A5 ~~~ A6
  end
  subgraph B["Area B · 750 neurons"]
    direction TB
    subgraph B23[" "]
      direction LR
      b23l["L23"]:::layer ~~~ b23e["E 200"]:::E ~~~ b23p["PV 25"]:::PV ~~~ b23s["SOM 15"]:::SOM ~~~ b23v["VIP 10"]:::VIP
    end
    subgraph B4[" "]
      direction LR
      b4l["L4"]:::layer ~~~ b4x["none (agranular)"]:::none
    end
    subgraph B5[" "]
      direction LR
      b5l["L5"]:::layer ~~~ b5e["E 200"]:::E ~~~ b5p["PV 25"]:::PV ~~~ b5s["SOM 15"]:::SOM ~~~ b5v["VIP 10"]:::VIP
    end
    subgraph B6[" "]
      direction LR
      b6l["L6"]:::layer ~~~ b6e["E 200"]:::E ~~~ b6p["PV 25"]:::PV ~~~ b6s["SOM 15"]:::SOM ~~~ b6v["VIP 10"]:::VIP
    end
    B23 ~~~ B4 ~~~ B5 ~~~ B6
  end
  A <-- "each way: E → E, PV<br>p 0.02 · 5.7 ms" --> B
  classDef E fill:#595289,stroke:#595289,color:#fff
  classDef PV fill:#af143c,stroke:#af143c,color:#fff
  classDef SOM fill:#e08a1e,stroke:#e08a1e,color:#fff
  classDef VIP fill:#2e8b57,stroke:#2e8b57,color:#fff
  classDef none fill:none,stroke:none,color:#777
  classDef layer fill:none,stroke:none,color:#333,font-weight:bold
  style A fill:#f4f4f6,stroke:#888,color:#333
  style B fill:#f4f4f6,stroke:#888,color:#333
  style A23 fill:#fff,stroke:#ccc
  style A4 fill:#fff,stroke:#ccc
  style A5 fill:#fff,stroke:#ccc
  style A6 fill:#fff,stroke:#ccc
  style B23 fill:#fff,stroke:#ccc
  style B4 fill:none,stroke:#ccc,stroke-dasharray:4 3
  style B5 fill:#fff,stroke:#ccc
  style B6 fill:#fff,stroke:#ccc
```

| Area | Layers | Cell types | Neurons per layer |
| :--- | :--- | :--- | :--- |
| A | L23, L4, L5, L6 | E, PV, SOM | E 200, PV 25, SOM 15 |
| B | L23, L5, L6 | E, PV, SOM, VIP | E 200, PV 25, SOM 15, VIP 10 |

Populations are named `<area>__<layer>_<cell type>`, e.g. `B__L23_VIP`. The `<area>__` prefix is what the analysis uses to plot each area on its own.

## Neuron entries

Populations of one cell type can share a neuron entry or have one per layer group, and the choice can differ between areas:

| Neuron entry | Populations | Differs from the base neuron in |
| :--- | :--- | :--- |
| `A_E` | A: E in every layer | nothing |
| `A_PV_upper` | A: PV in L23, L4 | C_m, tau_m, t_ref |
| `A_PV_deep` | A: PV in L5, L6 | as `A_PV_upper`, but a different C_m |
| `A_SOM` | A: SOM in every layer | C_m, tau_m, tau_syn_in |
| `B_E_upper` | B: E in L23 | tau_syn_ex = 2 ms, tau_syn_in = 4 ms |
| `B_E_deep` | B: E in L5, L6 | C_m, tau_m |
| `B_PV`, `B_SOM`, `B_VIP` | B: one entry per type, every layer | C_m, tau_m (and t_ref for PV) |

All are `iaf_psc_exp`; the base neuron is that of PD14.

## Connections

- **Within an area:** a probability per source type and target type (PV inhibits E and PV, SOM all but SOM, VIP mostly SOM), times 1 within a layer and 0.2 between layers.
- **Between areas:** only E cells project, onto E and PV cells of every layer of the other area, with probability 0.02 and a delay of distance / conduction speed (20 mm at 3.5 mm/ms).
- **Weights:** PSPs of 0.5 mV (E) and −1 mV (PV, SOM, VIP), 10 % spread, written as the currents (pA) that give them with each target's neuron (`current()` in `build.py`); delays 1.5 ms (E) and 0.75 ms (inhibitory), 50 % spread.
- **Background:** Poisson input at 8 spikes/s per synapse, with an indegree per cell type tuned so every population fires at about 3–16 spikes/s.

The reference rates in `reference.yaml` are the mean of four 2 s runs of this network; they are needed for the DC compensation when the network is scaled.

## Advanced variant

`microcircuit-lab generate toy_two_areas --advanced` writes `configs/network/toy_two_areas_advanced/`: the same areas, populations and probabilities, with the optional features of the config files turned on, as an example to copy:

| Feature | Where | In this network |
| :--- | :--- | :--- |
| Values drawn per neuron | `neurons.yaml`, `populations.yaml` | each neuron's `V_th` (normal, 1 mV spread); starting `V_m` uniform between `V_reset` and `V_th` |
| Connection rules | `connectivity.yaml` | `pairwise_bernoulli` with the probability within an area (no neuron connected to itself); `fixed_indegree` between areas |
| Synapse models | `synapses.yaml` | between areas, a depressing `tsodyks2_synapse`, with lognormal delays |
| Receptor ports | `synapses.yaml`, `neurons.yaml` | `B__L23_E` is an `iaf_psc_exp_multisynapse` neuron with a port for excitatory (2 ms), inhibitory (4 ms) and input from the other area (20 ms, depressing); its PSPs are converted with the time constant of their port, and its background input names a port too |

Its rates differ from those above. It has no `scaling.yaml` (it runs at full scale) and no reference rates, so a scaled copy needs `compensate_recurrent_input: false` in its `scaling.yaml`.

## Files

- `data.py`: every number above, as small tables.
- `build.py`: turns the tables into `configs/network/toy_two_areas/` (`main(argv)` is the entry point `microcircuit-lab generate` calls).
- `advanced.py`: the advanced variant, built from the same tables and functions.
- `clustered.py`: the clustered variant, built the same way.

## Clustered variant

`microcircuit-lab generate toy_two_areas --clusters 3` writes `configs/network/toy_two_areas_clustered/`: the same network with every population split into Q clusters (`A__L23_E__c0`, `A__L23_E__c1`, ...), following a common rule for clustered networks:

| What | Rule | In this network (Q = 3) |
| :--- | :--- | :--- |
| Cluster size | ceil(N / Q) neurons | E 200 → 67, PV 25 → 9, SOM 15 → 5, VIP 10 → 4 |
| Synapses | each connection split over every pair of a source and a target cluster, ceil(n_synapses / Q²) each | 302 connections → 2,718 |
| E → E weights | × `J_E_plus` within a cluster (cluster i to cluster i), × `J_E_minus = (Q − J_E_plus) / (Q − 1)` between clusters | × 2 and × 0.5 |
| Weights with an inhibitory source or target | × `J_I_plus = 1 + R_J (J_E_plus − 1)` within, × `J_I_minus = (Q − J_I_plus) / (Q − 1)` between | `R_J` = 0.75: × 1.75 and × 0.625 |
| Between areas | the same rule with its own `J_E_plus` and `R_J`; cluster i of one area pairs with cluster i of the other | the same values as within an area |
| Background | each neuron keeps its background indegree; the clusters of a population share one Poisson generator (`generator:`), and each neuron still gets its own spike train | 24 generators for 72 populations |

The minus factors keep each neuron's mean input as without clusters (the factors over the Q source clusters average to 1); `J_E_plus` must stay below Q. Rounding up changes the input of the small populations: PV clusters have 27 neurons instead of 25, and a small connection split nine ways gets at least one synapse per cluster pair (the inhibitory input of VIP grows by about half). The rates stay close to those of `toy_two_areas`. The numbers are in `data.py`. Like the advanced variant, it has no `scaling.yaml` and no reference rates.
