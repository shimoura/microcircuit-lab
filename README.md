# Microcircuit Lab

Microcircuit Lab is a configuration-driven framework for building, simulating, and analyzing recurrent neural microcircuit models. It separates **model-specific data**, **generic network representation**, and **simulator backends** so published models can share the same simulation infrastructure.

Full documentation lives in [`microcircuit_lab/README.md`](microcircuit_lab/README.md): architecture, installation, configuration, adding a new model, adding a backend, and everything else.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,nest]"
```

NEST isn't pinned as a hard dependency, since how you get it depends heavily on where you run (PyPI, conda-forge, or building from source on a cluster) -- see [`microcircuit_lab/README.md`](microcircuit_lab/README.md#installation) for the alternatives. All that matters is `import nest` works in the environment you run simulations in. Then run the bundled `toy` network, a minimal two-population (E/I) example:

```bash
microcircuit-lab run --network toy
```

See [`microcircuit_lab/README.md`](microcircuit_lab/README.md) for everything else.

To use the framework in your own project, install it and keep only your own builders, analyses and configs in the project folder (see "Starting a project" in `microcircuit_lab/README.md`). To change the framework itself, see [CONTRIBUTING.md](CONTRIBUTING.md).
