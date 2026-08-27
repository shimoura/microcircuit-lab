"""Generate network/simulation configs for a registered model.

Each model owns its own arguments; run `python scripts/generate.py <model>
--help` to see them. Adding a new model requires no changes here -- drop a
new subpackage under `microcircuit_lab/generators/` with a `generator.py`
that exposes `add_cli`, and it's picked up automatically via
`microcircuit_lab.generators.GENERATOR_REGISTRY`.
"""

import argparse

from microcircuit_lab.generators import GENERATOR_REGISTRY


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate configs for a Microcircuit Lab model.")
    subparsers = parser.add_subparsers(dest="model", required=True)

    for name, add_cli in GENERATOR_REGISTRY.items():
        subparser = subparsers.add_parser(name)
        add_cli(subparser)

    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
