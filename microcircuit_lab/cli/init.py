"""Create the folders of a new project, with an example.

    microcircuit-lab init <project>               # builders/, analyses/, configs/, experiments/, extensions/, and the toy example
    microcircuit-lab init <project> --with-core   # also a copy of the core, and every example

Nothing that already exists is touched. Plain ``init`` copies the toy network
twice, once per way of working: ``configs/network/toy`` written by hand, with
comments, and ``builders/toy``, which writes the same network to
``configs/network/toy_from_builder``; with the toy's simulation and analysis
settings, and the Brian2 models of ``extensions/brian2`` if Brian2 is installed.
They are fetched from the core repository, at the release of the installed
version, as ``--with-core`` does. With ``--with-core`` the core (the release
of the installed version, or the latest ``main`` if it has none) is copied into
``<project>/microcircuit-lab/`` and installed in editable mode. The copy is part of
the project: it can be read, changed and committed with the project's own code, and
the project's git commit then records the core's code too. Only the backends of
the installed simulators are copied (``--backends nest brian2`` to choose); running
``init --with-core --backends <name>`` again adds a missing one to an existing copy.

``--with-core`` also copies the examples into the project: every builder
under ``builders/``, every network, simulation and analysis config under
``configs/``, and the example models under ``extensions/``. They can then be run as they are (``run --network <name>``) or
regenerated first (``generate <builder>``). An example whose name already exists
in the project is skipped, so ``init .`` is safe in an existing repository.
"""

import argparse
import importlib.util
import shutil
import subprocess
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path

PROJECT_FOLDERS = ("builders", "analyses", "configs", "experiments", "extensions")
CORE_URL = "https://github.com/shimoura/microcircuit-lab.git"
CORE_FOLDER = "microcircuit-lab"
BACKENDS = ("nest", "brian2")
EXAMPLE_FOLDERS = ("builders", "configs/network", "configs/simulation", "configs/analysis", "extensions")
# What the copy of the core needs to be installed and edited: the package, its
# docs (the README links to them), and the files pyproject.toml names (readme, license).
CORE_FILES = ("microcircuit_lab", "docs", "pyproject.toml", "README.md", "LICENSE", "CITATION.cff")
# What plain init copies from the core repository.
TOY_EXAMPLE = (
    "builders/toy",
    "configs/network/toy",
    "configs/network/toy_from_builder",
    "configs/simulation/toy.yaml",
    "configs/analysis/toy.yaml",
)


def _ignore_build_files(project: Path) -> None:
    """``pip install -e`` writes ``microcircuit_lab.egg-info/`` into the copy;
    it is build output, not code to commit."""
    gitignore = project / ".gitignore"
    entry = "*.egg-info/"
    lines = gitignore.read_text().splitlines() if gitignore.exists() else []
    if entry not in lines:
        gitignore.write_text("\n".join([*lines, entry]) + "\n")


def _git(source: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(source), *arguments], check=True, capture_output=True, text=True
    ).stdout.strip()


def _installed_backends() -> list[str]:
    """The backends whose simulator is installed (looked up without importing it:
    NEST prints a banner and is slow); both if none is."""
    found = [name for name in BACKENDS if importlib.util.find_spec(name) is not None]
    if not found:
        print("No simulator found; copying every backend.")
    return found or list(BACKENDS)


def _copy(entry: Path, target: Path, skipped: set[Path] = frozenset()) -> None:
    """Copy a file or folder, leaving out ``__pycache__`` and the ``skipped`` paths."""
    if entry.is_dir():
        shutil.copytree(
            entry,
            target,
            ignore=lambda folder, names: [
                name for name in names if name == "__pycache__" or Path(folder, name) in skipped
            ],
        )
    else:
        shutil.copy2(entry, target)


def _copy_core(source: Path, core: Path, backends: list[str]) -> None:
    core.mkdir(parents=True)
    not_chosen = {source / "microcircuit_lab" / "backends" / name for name in BACKENDS if name not in backends}
    for name in CORE_FILES:
        if (source / name).exists():
            _copy(source / name, core / name, not_chosen)
    # The copy has no git history: record the commit it holds where setuptools-scm
    # reads it without one (as in a GitHub source archive), so the copy installs
    # under its own version (v0.1.0 -> 0.1.0, 4 commits past it -> 0.1.1.dev4+g<commit>).
    (core / ".git_archival.txt").write_text(
        f"node: {_git(source, 'rev-parse', 'HEAD')}\n"
        f"node-date: {_git(source, 'log', '-1', '--format=%cI')}\n"
        f"describe-name: {_git(source, 'describe', '--tags', '--match', '*[0-9]*')}\n"
    )
    print(f"Copied the core into {core} (backends: {', '.join(backends)})")


def _add_backends(source: Path, core: Path, backends: list[str]) -> None:
    """Add the chosen backends that an existing copy of the core lacks; nothing else changes."""
    for name in backends:
        target = core / "microcircuit_lab" / "backends" / name
        if not target.exists():
            _copy(source / "microcircuit_lab" / "backends" / name, target)
            print(f"Added the {name} backend to {core}")


def _copy_example(core: Path, project: Path, path: str) -> None:
    """Copy ``core/<path>`` to ``project/<path>``, unless the project has it."""
    target = project / path
    if target.exists():
        print(f"Skipped {path} (already exists)")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    _copy(core / path, target)
    print(f"Copied {path}")


def _copy_examples(core: Path, project: Path, backends: list[str]) -> None:
    not_chosen = {core / "extensions" / name for name in BACKENDS if name not in backends}
    for folder in EXAMPLE_FOLDERS:
        source = core / folder
        if not source.is_dir():
            continue
        for entry in sorted(source.iterdir()):
            if entry.name.startswith("__") or entry in not_chosen:
                continue
            _copy_example(core, project, f"{folder}/{entry.name}")


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


def _clone_core(source: Path) -> None:
    """Clone the core repository into ``source``, at the release of the
    installed version (the latest main if it has none)."""
    tag = _release_tag()
    # The commits and tags, without the files of old commits: enough to
    # name the version of the commit copied (see _copy_core).
    branch = [] if tag is None else ["--branch", tag]
    if tag is None:
        print("The installed version has no release tag; using the latest main instead.")
    subprocess.run(["git", "clone", "--quiet", "--filter=blob:none", *branch, CORE_URL, str(source)], check=True)


def _copy_toy(project: Path) -> None:
    """Copy the toy example (see the module docstring). Without git or a
    connection, the project keeps its empty folders and says why."""
    paths = list(TOY_EXAMPLE)
    # NEST has the toy's neuron built in; Brian2 takes it from extensions/brian2.
    if importlib.util.find_spec("brian2") is not None:
        paths.append("extensions/brian2")
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "core"
        try:
            _clone_core(source)
        except OSError:
            print(f"The toy example was not copied: git is not installed. Install it, then run `microcircuit-lab init {project}` again.")
            return
        except subprocess.CalledProcessError:
            print(
                f"The toy example was not copied: git could not reach {CORE_URL}. "
                f"Run `microcircuit-lab init {project}` again once you are online."
            )
            return
        for path in paths:
            # An older release may not have every part of the example.
            if (source / path).exists():
                _copy_example(source, project, path)


def _install_core(project: Path, backends: list[str]) -> None:
    core = project / CORE_FOLDER
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "core"
        _clone_core(source)
        if core.exists():
            print(f"{core} already exists, left as it is.")
            _add_backends(source, core, backends)
        else:
            _copy_core(source, core, backends)
        _copy_examples(source, project, backends)
    subprocess.run([sys.executable, "-m", "pip", "install", "-e", str(core)], check=True)
    _ignore_build_files(project)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="microcircuit-lab init", description="Create the folders of a new project, with the toy example."
    )
    parser.add_argument("project", type=Path)
    parser.add_argument(
        "--with-core",
        action="store_true",
        help=(
            f"Copy the core into <project>/{CORE_FOLDER}/, install it in editable mode "
            "and copy the example builders, configs and models into the project."
        ),
    )
    parser.add_argument(
        "--backends",
        nargs="+",
        choices=BACKENDS,
        help="Backends to copy with --with-core (default: those of the installed simulators).",
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
        _install_core(args.project, args.backends or _installed_backends())
    else:
        _copy_toy(args.project)
