"""Generate a model's config files.

    microcircuit-lab generate                 # list available models
    microcircuit-lab generate <model> --help  # that model's options
    microcircuit-lab generate <model> [opts]  # generate

Any subpackage under ``builders/`` that exposes a callable
``main(argv=None)`` is found automatically: there is nothing to
register and nothing to change in this file when a model is added. This
command just forwards the remaining arguments to that ``main``; each
builder owns its own argument parsing. Run it from the project root.
"""

import sys

from microcircuit_lab.project_code import discover_builders


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    builders = discover_builders()
    names = sorted(builders)

    if not argv or argv[0] in ("-h", "--help"):
        listing = "\n".join(f"  {name}" for name in names) or "  (none found)"
        print(f"Available models:\n{listing}")
        print("\nRun `microcircuit-lab generate <model> --help` for a model's options.")
        return

    name, rest = argv[0], argv[1:]
    if name not in builders:
        sys.exit(f"Unknown model {name!r}. Available: {', '.join(names) or '(none)'}")

    builders[name](rest)

