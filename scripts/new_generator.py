"""Scaffold a new model generator package.

Creates `microcircuit_lab/generators/<name>/` with the skeleton every
existing generator (humam, pd14) already follows -- `generator.py` with
`add_cli`, so it's picked up automatically by
`microcircuit_lab.generators.GENERATOR_REGISTRY`, plus a matching test
stub under `tests/`. Fill in the `# TODO` markers in the generated
`generator.py` with the actual data-translation logic for the new model.

Usage: python scripts/new_generator.py <name>
"""

import argparse
import keyword
from pathlib import Path

GENERATORS_DIR = Path(__file__).resolve().parent.parent / "microcircuit_lab" / "generators"
TESTS_DIR = Path(__file__).resolve().parent.parent / "tests"

INIT_TEMPLATE = '''"""{title} model support and configuration generation."""

from .generator import generate_{name}_configs

__all__ = ["generate_{name}_configs"]
'''

GENERATOR_TEMPLATE = '''"""Generate network configs for the {title} model.

# TODO: describe where the source data for this model comes from and what
# generate_{name}_configs() derives (e.g. only connectivity.yaml, or the
# full network config tree).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from microcircuit_lab.io.files import write_yaml


def _build_{name}() -> dict[str, Any]:
    """Translate this model's raw source data into config-ready data.

    # TODO: replace this stub with the real translation logic, returning
    # data shaped for the config file(s) generate_{name}_configs() writes.
    """

    raise NotImplementedError("_build_{name} has not been implemented yet")


def generate_{name}_configs(
    *,
    config_dir: str | Path = "configs",
    network_name: str = "{name}",
) -> Path:
    """Write the {title} network config and return its path.

    # TODO: adjust which file(s) this writes -- a single YAML like PD14's
    # connectivity-only generator, or the full network config tree like
    # HuMAM's, depending on how much of this model is derived vs. static.
    """

    output_path = Path(config_dir) / "network" / network_name / "connectivity.yaml"
    data = _build_{name}()
    write_yaml(output_path, data)
    return output_path


def _add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config-dir", default="configs")
    parser.add_argument("--network-name", default="{name}")


def _run(args: argparse.Namespace) -> None:
    output_path = generate_{name}_configs(
        config_dir=args.config_dir,
        network_name=args.network_name,
    )
    print(f"Generated config: {{output_path}}")


def add_cli(subparser: argparse.ArgumentParser) -> None:
    """Register {title} generation arguments on a ``scripts/generate.py`` subparser."""

    _add_arguments(subparser)
    subparser.set_defaults(func=_run)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the {title} network config from source data.",
    )
    _add_arguments(parser)
    args = parser.parse_args()
    _run(args)


if __name__ == "__main__":
    main()
'''

README_TEMPLATE = """# {title}

# TODO: describe this model -- what it represents, where its source data
# comes from, and any citation for the original reference.

## Usage

```bash
python scripts/generate.py {name} --help
```

## Data

# TODO: describe what's under `data/` (if anything) and how it was obtained.
"""

TEST_TEMPLATE = '''"""Tests for {title} configuration generation."""

from pathlib import Path

import yaml

from microcircuit_lab.generators.{name} import generate_{name}_configs


def test_generate_{name}_configs_writes_valid_yaml(tmp_path: Path) -> None:
    output_path = generate_{name}_configs(config_dir=tmp_path, network_name="{name}_test")

    data = yaml.safe_load(output_path.read_text())
    assert data
'''


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="model name, e.g. 'my_model' (used as the package/CLI name)")
    return parser.parse_args()


def _validate_name(name: str) -> None:
    if not name.isidentifier() or keyword.iskeyword(name):
        raise SystemExit(f"'{name}' is not a valid Python identifier for a package name.")

    if name != name.lower():
        raise SystemExit(f"'{name}' should be lowercase, to match the other model packages.")

    if (GENERATORS_DIR / name).exists():
        raise SystemExit(f"microcircuit_lab/generators/{name}/ already exists.")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    print(f"Created {path}")


def scaffold(name: str) -> None:
    _validate_name(name)

    title = name.replace("_", " ").title()
    package_dir = GENERATORS_DIR / name

    _write(package_dir / "__init__.py", INIT_TEMPLATE.format(name=name, title=title))
    _write(package_dir / "generator.py", GENERATOR_TEMPLATE.format(name=name, title=title))
    _write(package_dir / "README.md", README_TEMPLATE.format(name=name, title=title))
    _write(TESTS_DIR / f"test_{name}.py", TEST_TEMPLATE.format(name=name, title=title))

    print(
        f"\nNext steps:\n"
        f"  1. Fill in the TODOs in microcircuit_lab/generators/{name}/generator.py\n"
        f"  2. Fill in microcircuit_lab/generators/{name}/README.md\n"
        f"  3. Update tests/test_{name}.py to match what generate_{name}_configs actually does\n"
        f"  4. Run: python scripts/generate.py --help  # '{name}' should already be listed"
    )


def main() -> None:
    args = _parse_args()
    scaffold(args.name)


if __name__ == "__main__":
    main()
