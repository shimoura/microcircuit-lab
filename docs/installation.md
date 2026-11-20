# Installation

```bash title="Terminal"
python -m venv .venv
source .venv/bin/activate
pip install "microcircuit_lab[nest] @ git+https://github.com/shimoura/microcircuit-lab"
microcircuit-lab --version
```

This installs the latest version, with NEST. You need Python 3.11 or newer (3.12 for Brian2).

| Optional: you want | Install |
| :--- | :--- |
| a fixed version | add its tag from the [releases](https://github.com/shimoura/microcircuit-lab/releases): `...microcircuit-lab@<tag>` |
| NEST from conda-forge | `mamba install -c conda-forge nest-simulator`, then the line above without `[nest]` |
| NEST from source, or with MPI | see [NEST](nest.md) |
| Brian2 | `[brian2]` instead of, or next to, `[nest]`; see [Brian2](brian2.md) |
| the multitaper power spectrum | `[multitaper]` (it needs `mne`) |

However you get NEST, all that matters is that `import nest` works.

## Next

Make a project folder and run the toy network:

```bash title="Terminal"
microcircuit-lab init my_project --with-core   # --with-core (optional): also a copy of the core, to read and change
cd my_project
microcircuit-lab run --network toy
```

What `init` puts in the project: [Your project](project.md).

## Working on the core itself

Clone the repository and install it editable:

```bash title="Terminal"
git clone https://github.com/shimoura/microcircuit-lab
cd microcircuit-lab
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,nest]"
```

The rest is in [CONTRIBUTING.md](https://github.com/shimoura/microcircuit-lab/blob/main/CONTRIBUTING.md).
