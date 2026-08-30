"""Create microcircuit_lab/generators/<name>/ with a main() stub, plus a
default configs/simulation/<name>.yaml so the model runs the moment its
network directory exists.

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

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATORS_DIR = REPO_ROOT / "microcircuit_lab" / "generators"
SIMULATION_DIR = REPO_ROOT / "configs" / "simulation"

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

# Kept short and generic on purpose: execution settings (simulated time,
# threads, what to record) are not model-specific, so a new model starts
# from the same defaults and edits only what it needs.
SIMULATION_YAML = '''\
# Execution profile for `python scripts/run_simulation.py --network {name}`.
# Written from a default when the generator was scaffolded -- edit freely.
t_sim: 1000.0
resolution: 0.1
rng_seed: 42
local_num_threads: 4
print_time: true

recording:
  spike_recording: true
  voltage_recording: false
  voltage_interval: 1.0

output:
  output_dir: "output/{name}"
  overwrite: false
  save_metadata: true
  save_config: true
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

    simulation_yaml = SIMULATION_DIR / f"{name}.yaml"
    if simulation_yaml.exists():
        print(f"Kept existing {simulation_yaml}")
    else:
        simulation_yaml.write_text(SIMULATION_YAML.format(name=name))
        print(f"Created {simulation_yaml}")

    print(
        f"Next: implement main(), then `python scripts/generate.py {name}`. "
        f"Add a README.md and tests/test_{name}.py once the generator settles."
    )


if __name__ == "__main__":
    main()
