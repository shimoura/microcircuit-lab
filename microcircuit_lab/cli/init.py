"""Create the folders of a new project, with the toy example.

    microcircuit-lab init <project>                   # builders/, analyses/, configs/, experiments/, extensions/, and the toy example
    microcircuit-lab init <project> --example pd14    # also the pd14 example (--example can be given several times)
    microcircuit-lab init <project> --with-core       # also a copy of the core

Nothing that already exists is touched, so ``init .`` is safe in an existing
repository. Everything is fetched from the core repository, at the release of
the installed version (the latest ``main`` if it has none).

Plain ``init`` copies the toy network twice, once per way of working:
``configs/network/toy`` written by hand, with comments, and ``builders/toy``,
which writes the same network to ``configs/network/toy_from_builder``; with the
toy's simulation and analysis settings, and its models for the installed
simulators (``extensions/brian2``).

``--example <name>`` copies one of the core repository's ``examples/<name>/``
into the project's folders: its builder, networks, simulation and analysis
settings, plots, experiments and models, each where the project keeps it
(``builders/pd14``, ``configs/network/pd14``, ...). An item the project already
has, such as ``builders/pd14``, is skipped as a whole.

With ``--with-core`` the core is copied into ``<project>/microcircuit-lab/`` and
installed in editable mode. The copy is part of the project: it can be read,
changed and committed with the project's own code, and the project's git commit
then records the core's code too. Only the backends of the installed simulators
are copied (``--backends nest brian2`` to choose); running ``init --with-core
--backends <name>`` again adds a missing one to an existing copy.
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
# The folders of an example whose entries are copied one by one, each to the
# same place in the project: a builder, a network, a plot, a model file, ...
EXAMPLE_FOLDERS = (
    "builders", "analyses", "experiments", "configs/network", "configs/simulation", "configs/analysis",
    *(f"extensions/{name}" for name in BACKENDS),
)
# What the copy of the core needs to be installed and edited: the package, its
# docs (the README links to them), and the files pyproject.toml names (readme, license).
CORE_FILES = ("microcircuit_lab", "docs", "pyproject.toml", "README.md", "LICENSE", "CITATION.cff")
# What plain init copies from examples/toy, with the toy's models (see _example_items).
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


def _example_items(example: Path, backends: list[str]) -> list[str]:
    """Every item of an example (see EXAMPLE_FOLDERS), leaving out the
    packages' ``__init__.py`` and the models of the simulators not chosen."""
    items = []
    for folder in EXAMPLE_FOLDERS:
        if folder.startswith("extensions/") and folder.split("/")[1] not in backends:
            continue
        if (example / folder).is_dir():
            items += [f"{folder}/{entry.name}" for entry in sorted((example / folder).iterdir())
                      if not entry.name.startswith("__")]
    return items


def _copy_example(example: Path, project: Path, items: list[str]) -> None:
    """Copy each item of ``example`` to the same place in ``project``, unless the project has it."""
    for item in items:
        target = project / item
        # A model file several examples share is already there: nothing to say.
        if target.is_file() and target.read_bytes() == (example / item).read_bytes():
            continue
        if target.exists():
            print(f"Skipped {item} (already exists)")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        _copy(example / item, target)
        print(f"Copied {item}")


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


def _install_core(source: Path, project: Path, backends: list[str]) -> None:
    core = project / CORE_FOLDER
    if core.exists():
        print(f"{core} already exists, left as it is.")
        _add_backends(source, core, backends)
    else:
        _copy_core(source, core, backends)
    subprocess.run([sys.executable, "-m", "pip", "install", "-e", str(core)], check=True)
    _ignore_build_files(project)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="microcircuit-lab init", description="Create the folders of a new project, with the toy example."
    )
    parser.add_argument("project", type=Path)
    parser.add_argument(
        "--example",
        action="append",
        default=[],
        metavar="NAME",
        help="Also copy the example NAME (e.g. pd14) into the project's folders; can be given several times.",
    )
    parser.add_argument(
        "--with-core",
        action="store_true",
        help=f"Also copy the core into <project>/{CORE_FOLDER}/ and install it in editable mode.",
    )
    parser.add_argument(
        "--backends",
        nargs="+",
        choices=BACKENDS,
        help="Simulators whose backend (with --with-core) and example models are copied "
        "(default: the installed ones).",
    )
    args = parser.parse_args(argv)

    for name in PROJECT_FOLDERS:
        folder = args.project / name
        if folder.exists():
            print(f"{folder} already exists, left as it is.")
        else:
            folder.mkdir(parents=True)
            print(f"Created {folder}")

    backends = args.backends or _installed_backends()
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "core"
        # Without git or a connection, the project keeps its empty folders and says why.
        try:
            _clone_core(source)
        except OSError:
            print("Nothing was copied from the core repository: git is not installed. "
                  f"Install it, then run `microcircuit-lab init {args.project}` again.")
            return
        except subprocess.CalledProcessError:
            print(f"Nothing was copied from the core repository: git could not reach {CORE_URL}. "
                  f"Run `microcircuit-lab init {args.project}` again once you are online.")
            return

        examples = source / "examples"
        unknown = [name for name in args.example if not (examples / name).is_dir()]
        if unknown:
            found = sorted(path.name for path in examples.iterdir() if path.is_dir())
            raise SystemExit(f"No example named {', '.join(unknown)}; the examples are: {', '.join(found)}.")

        toy = [item for item in _example_items(examples / "toy", backends)
               if item in TOY_EXAMPLE or item.startswith("extensions/")]
        _copy_example(examples / "toy", args.project, toy)
        for name in args.example:
            _copy_example(examples / name, args.project, _example_items(examples / name, backends))
        if args.with_core:
            _install_core(source, args.project, backends)
