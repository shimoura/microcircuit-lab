"""The ``microcircuit-lab`` command.

    microcircuit-lab init <project>            create a project's folders (--with-core: keep the core inside)
    microcircuit-lab generate <model> [opts]   write a model's network configs
    microcircuit-lab run [opts]                simulate a network and plot it
    microcircuit-lab new-builder <name>        scaffold ./builders/<name>/
    microcircuit-lab --version                 print the installed version (also -V)

Run it from the project root: builders, analyses and configs are looked up
in the current folder. Each subcommand lives in its own module and takes the
remaining arguments as ``main(argv)``.
"""

import sys
from importlib.metadata import version

from microcircuit_lab.cli import generate, init, new_builder, run

COMMANDS = {
    "init": init.main,
    "generate": generate.main,
    "run": run.main,
    "new-builder": new_builder.main,
}


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    if argv[0] in ("-V", "--version"):
        print(f"microcircuit-lab {version('microcircuit_lab')}")
        return
    command, rest = argv[0], argv[1:]
    if command not in COMMANDS:
        sys.exit(f"Unknown command {command!r}. Available: {', '.join(COMMANDS)}")
    COMMANDS[command](rest)
