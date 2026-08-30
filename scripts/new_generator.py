"""Create microcircuit_lab/generators/<name>/ with a main() stub.

A generator is any code whose output is a directory under
configs/network/<name>/ that passes microcircuit_lab.io.validate_network_config.
This just makes the package that `python scripts/generate.py` discovers --
implement main() however you like (see microcircuit_lab/generators/pd14/
for a minimal example, .../humam/ for a full one).

Usage: python scripts/new_generator.py <name>
"""

import keyword
import sys
from pathlib import Path

GENERATORS_DIR = Path(__file__).resolve().parent.parent / "microcircuit_lab" / "generators"

STUB = '''"""{title} model -- turns source data into configs/network/{name}/."""

from __future__ import annotations


def main(argv: list[str] | None = None) -> None:
    """Entry point for `python scripts/generate.py {name}`.

    Write configs/network/{name}/ from this model's source data -- the
    fields (with types, defaults, and which are required) are in
    microcircuit_lab/config/files.py; configs/network/toy/ is a small one
    to copy; microcircuit_lab/generators/pd14 (minimal) / .../humam (full)
    are worked generators. Then finish with:

        from microcircuit_lab.io import validate_network_config
        validate_network_config("configs/network/{name}")
    """
    raise NotImplementedError("Implement {name} config generation here.")
'''


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Usage: python scripts/new_generator.py <name>")

    name = sys.argv[1]
    if not name.isidentifier() or keyword.iskeyword(name) or name != name.lower():
        sys.exit(f"{name!r} must be a lowercase Python identifier.")

    package = GENERATORS_DIR / name
    if package.exists():
        sys.exit(f"{package} already exists.")

    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        STUB.format(name=name, title=name.replace("_", " ").title())
    )
    print(f"Created {package / '__init__.py'}")
    print(
        f"Next: implement main(), add a README.md and tests/test_{name}.py, "
        f"then run `python scripts/generate.py {name}`."
    )


if __name__ == "__main__":
    main()
