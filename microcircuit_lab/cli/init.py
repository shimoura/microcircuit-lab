"""Create the folders of a new project.

    microcircuit-lab init <project>               # builders/, analyses/, configs/, experiments/
    microcircuit-lab init <project> --with-core   # also keep a clone of the core inside

Nothing that already exists is touched. With ``--with-core`` the core is cloned
into ``<project>/microcircuit-lab/`` and installed in editable mode, so its code
sits next to the project's and can be read and edited; the folder is added to
``.gitignore`` because it is a clone of its own repository.
"""

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_FOLDERS = ("builders", "analyses", "configs", "experiments")
CORE_URL = "https://github.com/shimoura/microcircuit-lab.git"
CORE_FOLDER = "microcircuit-lab"


def _ignore_core_folder(project: Path) -> None:
    gitignore = project / ".gitignore"
    entry = f"{CORE_FOLDER}/"
    lines = gitignore.read_text().splitlines() if gitignore.exists() else []
    if entry not in lines:
        gitignore.write_text("\n".join([*lines, entry]) + "\n")


def _install_core(project: Path) -> None:
    core = project / CORE_FOLDER
    if core.exists():
        print(f"{core} already exists, left as it is.")
    else:
        subprocess.run(["git", "clone", CORE_URL, str(core)], check=True)
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
        help=f"Clone the core into <project>/{CORE_FOLDER}/ and install it in editable mode.",
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
