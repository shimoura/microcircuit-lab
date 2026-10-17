"""Generate a model's config files.

    python scripts/generate.py                 # list available models
    python scripts/generate.py <model> --help  # that model's options
    python scripts/generate.py <model> [opts]  # generate

Any subpackage under ``builders/`` that exposes a callable
``main(argv=None)`` is discovered automatically -- there is nothing to
register and nothing to change in this file when a model is added. This
dispatcher just forwards the remaining arguments to that ``main``; each
builder owns its own argument parsing. Run it from the repository root.
"""

import sys

from microcircuit_lab.io import discover_builders


def main() -> None:
    argv = sys.argv[1:]
    builders = discover_builders()
    names = sorted(builders)

    if not argv or argv[0] in ("-h", "--help"):
        listing = "\n".join(f"  {name}" for name in names) or "  (none found)"
        print(f"Available models:\n{listing}")
        print("\nRun `python scripts/generate.py <model> --help` for a model's options.")
        return

    name, rest = argv[0], argv[1:]
    if name not in builders:
        sys.exit(f"Unknown model {name!r}. Available: {', '.join(names) or '(none)'}")

    builders[name](rest)


if __name__ == "__main__":
    main()
