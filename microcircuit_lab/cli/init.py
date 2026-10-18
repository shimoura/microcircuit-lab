"""Create the folders of a new project.

    microcircuit-lab init <project>               # builders/, analyses/, configs/, experiments/
    microcircuit-lab init <project> --with-core   # also keep a clone of the core inside

Nothing that already exists is touched. With ``--with-core`` the core is cloned
into ``<project>/microcircuit-lab/`` and installed in editable mode, so its code
sits next to the project's and can be read and edited; the folder is added to
``.gitignore`` because it is a clone of its own repository.

``--with-core`` also copies the clone's examples into the project: every builder
under ``builders/`` and every network, simulation and analysis config under
``configs/``. They can then be run as they are (``run --network <name>``) or
regenerated first (``generate <builder>``). An example whose name already exists
in the project is skipped, so ``init .`` is safe in an existing repository.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_FOLDERS = ("builders", "analyses", "configs", "experiments")
CORE_URL = "https://github.com/shimoura/microcircuit-lab.git"
CORE_FOLDER = "microcircuit-lab"
EXAMPLE_FOLDERS = ("builders", "configs/network", "configs/simulation", "configs/analysis")


def _ignore_core_folder(project: Path) -> None:
    gitignore = project / ".gitignore"
    entry = f"{CORE_FOLDER}/"
    lines = gitignore.read_text().splitlines() if gitignore.exists() else []
    if entry not in lines:
        gitignore.write_text("\n".join([*lines, entry]) + "\n")


def _copy_examples(core: Path, project: Path) -> None:
    for folder in EXAMPLE_FOLDERS:
        source = core / folder
        if not source.is_dir():
            continue
        for entry in sorted(source.iterdir()):
            if entry.name.startswith("__"):
                continue
            target = project / folder / entry.name
            if target.exists():
                print(f"Skipped {folder}/{entry.name} (already exists)")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if entry.is_dir():
                shutil.copytree(entry, target, ignore=shutil.ignore_patterns("__pycache__"))
            else:
                shutil.copy2(entry, target)
            print(f"Copied {folder}/{entry.name}")


def _install_core(project: Path) -> None:
    core = project / CORE_FOLDER
    if core.exists():
        print(f"{core} already exists, left as it is.")
    else:
        subprocess.run(["git", "clone", CORE_URL, str(core)], check=True)
    _copy_examples(core, project)
    subprocess.run([sys.executable, "-m", "pip", "install", "-e", str(core)], check=True)
    _ignore_core_folder(project)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="microcircuit-lab init", description="Create the folders of a new project."
    )
    parser.add_argument("project", type=Path)
    parser.add_argument(
        "--with-core",
        action="store_true",
        help=(
            f"Clone the core into <project>/{CORE_FOLDER}/, install it in editable mode "
            "and copy its example builders and configs into the project."
        ),
    )
    args = parser.parse_args(argv)

    for name in PROJECT_FOLDERS:
        folder = args.project / name
        if folder.exists():
            print(f"{folder} already exists, left as it is.")
        else:
            folder.mkdir(parents=True)
            print(f"Created {folder}")

    if args.with_core:
        _install_core(args.project)
