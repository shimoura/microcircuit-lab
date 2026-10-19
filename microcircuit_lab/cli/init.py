"""Create the folders of a new project.

    microcircuit-lab init <project>               # builders/, analyses/, configs/, experiments/
    microcircuit-lab init <project> --with-core   # also a copy of the core, and the examples

Nothing that already exists is touched. With ``--with-core`` the core (the release
of the installed version, or the latest ``main`` if it has none) is copied into
``<project>/microcircuit-lab/`` and installed in editable mode. The copy is part of
the project: it can be read, changed and committed with the project's own code, and
the project's git commit then records the core's code too.

``--with-core`` also copies the examples into the project: every builder
under ``builders/`` and every network, simulation and analysis config under
``configs/``. They can then be run as they are (``run --network <name>``) or
regenerated first (``generate <builder>``). An example whose name already exists
in the project is skipped, so ``init .`` is safe in an existing repository.
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path

PROJECT_FOLDERS = ("builders", "analyses", "configs", "experiments")
CORE_URL = "https://github.com/shimoura/microcircuit-lab.git"
CORE_FOLDER = "microcircuit-lab"
EXAMPLE_FOLDERS = ("builders", "configs/network", "configs/simulation", "configs/analysis")
# What the copy of the core needs to be installed and edited: the package, and
# the files pyproject.toml names (readme, license).
CORE_FILES = ("microcircuit_lab", "pyproject.toml", "README.md", "LICENSE", "CITATION.cff")


def _ignore_build_files(project: Path) -> None:
    """``pip install -e`` writes ``microcircuit_lab.egg-info/`` into the copy;
    it is build output, not code to commit."""
    gitignore = project / ".gitignore"
    entry = "*.egg-info/"
    lines = gitignore.read_text().splitlines() if gitignore.exists() else []
    if entry not in lines:
        gitignore.write_text("\n".join([*lines, entry]) + "\n")


def _copy_core(source: Path, core: Path) -> None:
    core.mkdir(parents=True)
    for name in CORE_FILES:
        entry = source / name
        if entry.is_dir():
            shutil.copytree(entry, core / name, ignore=shutil.ignore_patterns("__pycache__"))
        elif entry.is_file():
            shutil.copy2(entry, core / name)
    print(f"Copied the core into {core}")


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


def _release_tag() -> str | None:
    """The tag of the installed version (e.g. ``v0.1.0``) if the core repository
    has it, else None (e.g. a development version that was never released)."""
    tag = f"v{version('microcircuit_lab')}"
    found = subprocess.run(
        ["git", "ls-remote", "--tags", CORE_URL, f"refs/tags/{tag}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return tag if found.stdout.strip() else None


def _install_core(project: Path) -> None:
    core = project / CORE_FOLDER
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "core"
        tag = _release_tag()
        if tag is None:
            print("The installed version has no release tag; using the latest main instead.")
            subprocess.run(["git", "clone", "--depth", "1", CORE_URL, str(source)], check=True)
        else:
            subprocess.run(
                ["git", "clone", "--depth", "1", "--branch", tag, CORE_URL, str(source)],
                check=True,
            )
        if core.exists():
            print(f"{core} already exists, left as it is.")
        else:
            _copy_core(source, core)
        _copy_examples(source, project)
    subprocess.run([sys.executable, "-m", "pip", "install", "-e", str(core)], check=True)
    _ignore_build_files(project)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="microcircuit-lab init", description="Create the folders of a new project."
    )
    parser.add_argument("project", type=Path)
    parser.add_argument(
        "--with-core",
        action="store_true",
        help=(
            f"Copy the core into <project>/{CORE_FOLDER}/, install it in editable mode "
            "and copy the example builders and configs into the project."
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
