# Your project

A project is your own folder, usually a git repository of its own. `microcircuit-lab init my_project` makes one:

```text
my_project/
├── configs/            the network, simulation and analysis files
├── builders/           optional: code that writes network files
├── analyses/           optional: your own plots
├── experiments/        optional: your scripts (sweeps, several seeds, ...)
├── extensions/         optional: what you add to a simulator (models, rules, distributions)
├── output/             the runs, made by the first run
└── microcircuit-lab/   optional, with --with-core: your copy of the core
```

Run every command from this folder: that is where the core looks for these folders.

## What `init` copies

| Command | You get |
| :--- | :--- |
| `microcircuit-lab init my_project` | the folders and the toy network; the core stays in your Python environment |
| `... --example pd14` (optional) | also the `pd14` example: its builder, networks, settings, plots and models. Give it several times for several examples ([the list](https://github.com/shimoura/microcircuit-lab/tree/main/examples)) |
| `... --with-core` (optional) | also a copy of the core in `microcircuit-lab/`, installed in place of the one in your environment |

Everything comes from the core repository, at the release of the version you installed. If you installed from a clone (`pip install -e .`), it comes from your clone instead, as it is now, and `init` says so.

`init` leaves every file that exists as it is, so running it again in a project (`microcircuit-lab init .`) only adds what is missing. An example you already have in another version is not copied, and `init` says which file differs. After an upgrade that changes the file format, delete the toy's folders and run `init .` again to get them in the new format.

## The toy, two ways

The toy network comes twice, to show both ways of writing a network:

```bash title="Terminal"
microcircuit-lab run --network toy                  # configs/network/toy/: written by hand, with comments
microcircuit-lab generate toy                       # builders/toy/ writes configs/network/toy_from_builder/
microcircuit-lab run --network toy_from_builder --simulation toy --analysis toy
```

Both are the same network model and give the same spikes. For your own model: [A new network model](new-network.md).

## Your copy of the core (optional)

With `--with-core`, `microcircuit-lab/` is yours: read it, change it, commit it with your project. Your edits take effect at once, and each run records your project's git commit, which then covers the core too.

- A new release of the core does not change your copy; compare and merge it by hand if you want it.
- `--with-core` copies the backends of the simulators you have installed; `--backends nest brian2` chooses, and running it again adds a missing one.
- To change the core for everyone, see [CONTRIBUTING.md](https://github.com/shimoura/microcircuit-lab/blob/main/CONTRIBUTING.md). Change the core when an idea would help any model and the files can't say it (a new stimulus type, spatial structure); if only one model needs it, it belongs in that model's builder.
