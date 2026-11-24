# NEST

NEST is the default simulator. The same files run on NEST and Brian2; the simulation file's `backend` or `--backend` picks one:

```bash title="Terminal"
microcircuit-lab run --network toy                  # NEST
microcircuit-lab run --network toy --backend brian2 # Brian2
```

What becomes which NEST object (a population is `nest.Create`, a connection one `nest.Connect`, ...) is in [From a builder to the plots](workflow.md), step 2.

## Installing from source (optional)

NEST from source, e.g. on a cluster for MPI: see the [NEST installation docs](https://nest-simulator.readthedocs.io/en/stable/installation/index.html) and [`scripts/install_nest_from_source.sh`](https://github.com/shimoura/microcircuit-lab/blob/main/scripts/install_nest_from_source.sh) in the repository (`NEST_WITH_MPI=ON` for MPI). Only NEST built from source runs on several MPI processes; the pip and conda-forge builds use threads only.

## NESTML models (optional)

1. Write the model in `extensions/nestml/` (e.g. `extensions/nestml/my_lif.nestml`), and compile it once:
   ```python
   from pynestml.frontend.pynestml_frontend import generate_nest_target

   generate_nest_target(input_path="extensions/nestml/my_lif.nestml",
                        target_path="extensions/nestml/build/my_module", module_name="my_module")
   ```
2. Use it in `neurons.yaml` like any model, by the name NESTML gives it (e.g. `my_lif_nestml`), with weights in the unit of the variable they add to (see [Weights and delays](weights-and-delays.md)).
3. Load the module when running:
   ```python
   simulation = Simulation.from_yaml(
       network_name="toy_nestml",
       backend_options={"nest_modules": ["my_module"]},
   )
   ```
   or `microcircuit-lab run --network toy_nestml --nest-modules my_module`, or in the simulation file:
   ```yaml
   backend:
     name: nest
     options:
       nest_modules: [my_module]
   ```

Don't commit the compiled output; it depends on the platform and the NEST version.

## Several MPI processes (optional)

```bash title="Terminal"
mpirun -n 4 microcircuit-lab run --network pd14
```

- Needs NEST built from source with MPI (above), on a cluster against the cluster's MPI. Brian2 runs in one process.
- NEST spreads the neurons over the processes. Each process writes its own spike files into the same `recordings/` folder, so the processes must share a file system.
- The first process picks the run folder; when all have finished simulating, it alone prints the rates and writes `config.yaml`, `metadata.json` and the plots.
- In your own script, save or plot only where `simulation.is_main_process` is true.

## In Jupyter

NEST runs in a notebook as anywhere else. One thing to know: with `print_time: true`, NEST writes its progress line once per step of the shortest delay, while it holds the Python interpreter. The notebook reads that output through a small buffer (about 64 KB), so a run with many steps hangs the kernel: with 0.1 ms delays, a 100 ms run is fine and a 200 ms run hangs. For runs in a notebook, set `print_time: false` in the simulation file (or `settings["print_time"] = False` in your code); the toy's simulation file has it off. In a terminal or a script, the progress line is fine.

## Rules and distributions of NEST (optional)

Any rule or distribution NEST has can be named in the files, with its arguments as keys of their own: [Connections](connections.md) and [Other distributions](weights-and-delays.md#other-distributions-optional).
