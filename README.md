# Microcircuit Lab

Microcircuit Lab is a configuration-driven framework for building, simulating, and analyzing recurrent neural microcircuit models. It separates **model-specific data**, **generic network representation**, and **simulator backends** so published models can share the same simulation infrastructure.

Full documentation lives in [`microcircuit_lab/README.md`](microcircuit_lab/README.md): architecture, installation, configuration, adding a new model, adding a backend, and everything else.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

NEST must be available in the environment used to run simulations (see [`microcircuit_lab/README.md`](microcircuit_lab/README.md#installation) for a mamba/conda alternative). Then run the bundled `toy` network, a minimal two-population (E/I) example:

```bash
python scripts/run_simulation.py --network toy
```

See [`microcircuit_lab/README.md`](microcircuit_lab/README.md) for everything else.

This repository is meant to be forked as the starting point for a new, independent research project. When forking, replace this file with a short description of your own project and leave the framework documentation in `microcircuit_lab/README.md` untouched (see its "Using this as a template for a new project" section for details).
