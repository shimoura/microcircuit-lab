"""Generate network/simulation configs for a registered model.

Each model owns its own arguments; run `python scripts/generate.py <model>
--help` to see them. Adding a new model only requires registering it in
`microcircuit_lab.models.MODEL_GENERATORS` -- this script never changes.
"""

import argparse

from microcircuit_lab.models import MODEL_GENERATORS


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate configs for a Microcircuit Lab model.")
    subparsers = parser.add_subparsers(dest="model", required=True)

    for name, add_cli in MODEL_GENERATORS.items():
        subparser = subparsers.add_parser(name)
        add_cli(subparser)

    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
