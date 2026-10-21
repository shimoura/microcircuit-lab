# From a builder to the plots

`microcircuit-lab run --network <name>` goes through five steps, after an optional step 0 that writes the network. Each step turns one thing into the next:

```mermaid
%%{init: {"flowchart": {"rankSpacing": 22, "nodeSpacing": 20, "padding": 6, "wrappingWidth": 400}}}%%
flowchart TD
  B["your data and code<br/><i>if you write a builder</i>"]:::opt -.->|"0 · generate"| Y
  Y["YAML files<br/>configs/network/&lt;name&gt;/"] -->|"1 · check"| W["the network, as written"]
  W -->|"2 · prepare"| P["the network, ready to simulate"]
  P -->|"3 · simulate in NEST"| K["spikes"]
  K -->|"4 · save"| R["run folder<br/>output/&lt;name&gt;/&lt;date_time&gt;/"]
  R -->|"5 · plot"| G["plots/"]
  classDef opt stroke-dasharray: 5 4,fill:#ffffff
```

In the diagrams on this page, a dashed box runs only when *the condition in italics* holds; a solid box always runs. Paths of the code are inside `microcircuit_lab/`.

## 0 · Generate

**In:** your data and code. **Out:** the YAML files.

Optional: the YAML files can also be written by hand. A builder is a folder `builders/<model>/` with a `main(argv)`, run by `microcircuit-lab generate <model>`.

**Code:** `cli/generate.py`, `builder_tools.py`

## 1 · Check

**In:** the YAML files. **Out:** the network, as written.

Each file is checked against its own module (`connectivity.yaml` → `config/connectivity.py`, ...), then names are matched across files. A mistake stops the run before NEST starts, and names the file and the field:

```text
Invalid network config in configs/network/toy:
  connectivity.yaml: connections.0.weight.rel_std: Input should be greater than or equal to 0
```

What each field accepts: [config_files.md](config_files.md).

**Code:** `network/load.py`, `config/`

## 2 · Prepare

**In:** the network, as written. **Out:** the network, ready to simulate. The files themselves are not changed.

```mermaid
%%{init: {"flowchart": {"rankSpacing": 28, "nodeSpacing": 15, "padding": 5}}}%%
flowchart LR
  U["mV → pA<br/><i>if unit: PSP</i>"]:::opt --> K["scale<br/><i>if scaling.yaml</i>"]:::opt --> D["DC for input lost<br/><i>if scaling.yaml</i>"]:::opt --> R["rate × indegree<br/><b>always</b>"] --> M["constant current<br/><i>if mean_current</i>"]:::opt
  classDef opt stroke-dasharray: 5 4,fill:#ffffff
```

- **mV → pA:** a weight written as the size of a PSP becomes the current that gives it.
- **scale:** fewer neurons and synapses, stronger weights.
- **DC for input lost:** the mean input of the missing synapses, as a constant current.
- **rate × indegree:** each population's background is one Poisson generator, firing at the rate per synapse times the number of synapses.
- **constant current:** the background becomes its mean, a constant current.

So with weights in pA (`unit: PSC`) and no `scaling.yaml`, everything is simulated as written, except that the background rate is multiplied by the indegree. To see the two ends:

```python
from microcircuit_lab.network.load import read_network, load_network

written = read_network("configs/network/pd14")    # as written
prepared = load_network("configs/network/pd14")   # ready to simulate
```

**Code:** `network/prepare.py` (the order), `network/psp_psc_conversion.py`, `network/scaling.py`, `network/compensation.py`

## 3 · Simulate

**In:** the network, ready to simulate, and `configs/simulation/<name>.yaml`. **Out:** spikes.

NEST objects are created in this order, then the network is simulated:

```mermaid
%%{init: {"flowchart": {"rankSpacing": 28, "nodeSpacing": 15, "padding": 5}}}%%
flowchart LR
  S["synapses<br/><i>if synapses.yaml</i>"]:::opt --> N["populations<br/><b>always</b>"] --> R["recorders<br/><i>if recording</i>"]:::opt --> B["background<br/><i>if poisson</i>"]:::opt --> T["stimuli<br/><i>if stimuli.yaml</i>"]:::opt --> C["connections<br/><b>always</b>"]
  classDef opt stroke-dasharray: 5 4,fill:#ffffff
```

| In the files | In NEST |
| :--- | :--- |
| a synapse entry | a copy of its synapse model, under the entry's name |
| a population | its neurons: `nest.Create(model, size)` |
| `recording` in the simulation file | a `spike_recorder` (and a `multimeter` for voltages) |
| a background input | a `poisson_generator`, shared by populations with the same `generator:` |
| a stimulus | a `dc_generator`, `poisson_generator` or `inhomogeneous_poisson_generator` |
| a connection (one row) | one `nest.Connect`, with its rule, weight and delay |

**Code:** `backends/nest/simulator.py` (`build`: the order), `backends/nest/distributions.py` (drawn weights, delays and values)

## 4 · Save

**In:** spikes. **Out:** the run folder.

```text
output/<name>/<date_time>/
├── recordings/     spikes, written by NEST while it runs
├── config.yaml     the prepared network and the settings used
├── metadata.json   versions, git commits, spike counts, files
└── plots/          step 5
```

**Code:** `run_folder.py`

## 5 · Plot

**In:** the run folder, `configs/analysis/<name>.yaml` and your `analyses/`. **Out:** `plots/`.

To plot again, without simulating:

```bash
microcircuit-lab run --run-dir output/<name>/<date_time>
```

**Code:** `analysis/`

## Where to look when...

| ... | Look at |
| :--- | :--- |
| a file is refused | the module named after the file, in `config/` |
| a name "is not defined" | `network/load.py` (populations, neurons), `config/network.py` (synapses) |
| weights or sizes differ from the files | step 2: compare `read_network` and `load_network` |
| rates drop in a scaled run | `network/compensation.py`; full-scale rates in `reference.yaml` |
| something looks wrong in NEST | step 3: the `create_...` method for that part, in `backends/nest/simulator.py` |
| the run went to the wrong folder | the `output` section of the simulation file |
| your plot is not found | `register_plot` in your file in `analyses/` |
| `generate` does not list your builder | step 0: a `main(argv)` in `builders/<model>/__init__.py` |
| a large network loads slowly | `connections_file` (CSV), `config/connection_table.py` |

To change the core: [CONTRIBUTING.md](../CONTRIBUTING.md#changing-the-core).
