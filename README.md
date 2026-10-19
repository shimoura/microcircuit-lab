# Microcircuit Lab

Microcircuit Lab builds, simulates and analyses spiking network models of cortex, from a single microcircuit to multi-area models. A network is described in plain YAML files; the same core prepares it, runs it in NEST and analyses the result, whatever model it came from. Model-specific code lives apart, in *builders*, so published models share one tested simulation path.

The full documentation is in [`microcircuit_lab/README.md`](microcircuit_lab/README.md).

## Quick start

Install the core, start a project with the examples, and run the smallest one:

```bash
python -m venv .venv
source .venv/bin/activate
pip install "microcircuit_lab[nest] @ git+https://github.com/shimoura/microcircuit-lab@v0.1.0"

microcircuit-lab init my_project --with-core
cd my_project
microcircuit-lab run --network toy
```

The plots and spikes are saved in `output/toy/<timestamp>/`. `pd14`, `toy_two_areas` and the HuMAM networks run the same way. NEST can also come from conda-forge or a build from source; see [Installation](microcircuit_lab/README.md#installation).

A project holds your own builders, analyses and configs, and with `--with-core` your own copy of the core to change as you like; see [Starting a project](microcircuit_lab/README.md#starting-a-project). To propose a change to the core here, see [CONTRIBUTING.md](CONTRIBUTING.md).

## How to cite

If you use Microcircuit Lab in your work, please cite it. [`CITATION.cff`](CITATION.cff) has the reference; on GitHub, "Cite this repository" in the sidebar gives it in APA and BibTeX. Please also cite the papers of the models you use (listed in each builder's README).

## License

BSD 3-Clause, see [`LICENSE`](LICENSE).
