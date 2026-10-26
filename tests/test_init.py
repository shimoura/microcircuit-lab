"""`microcircuit-lab init`: project folders, never overwriting, --with-core (a copy of the core) and its examples."""

import subprocess
from pathlib import Path
from types import SimpleNamespace

from microcircuit_lab.cli import init


def _recorder(commands, tag_exists=True):
    """A stand-in for subprocess.run that records each command; `git ls-remote`
    answers as if the release tag exists (or not)."""

    def run(command, check, **kwargs):
        commands.append(command)
        return SimpleNamespace(stdout="abc123\trefs/tags/v0.1.0\n" if tag_exists else "")

    return run


def test_creates_the_project_folders(tmp_path):
    init.main([str(tmp_path / "proj")])
    for name in ("builders", "analyses", "configs", "experiments"):
        assert (tmp_path / "proj" / name).is_dir()


def test_existing_files_are_left_alone(tmp_path, capsys):
    (tmp_path / "builders").mkdir()
    (tmp_path / "builders" / "mine.py").write_text("keep")
    init.main([str(tmp_path)])
    assert (tmp_path / "builders" / "mine.py").read_text() == "keep"
    assert "already exists" in capsys.readouterr().out


def test_with_core_installs_the_copy_and_ignores_only_build_files(tmp_path, monkeypatch):
    commands = []
    monkeypatch.setattr(subprocess, "run", _recorder(commands))
    (tmp_path / ".gitignore").write_text("output/\n")
    init.main([str(tmp_path), "--with-core"])
    for name in init.BACKENDS:
        (tmp_path / init.CORE_FOLDER / "microcircuit_lab" / "backends" / name).mkdir(parents=True)
    init.main([str(tmp_path), "--with-core"])

    assert commands[0][:3] == ["git", "ls-remote", "--tags"]
    assert commands[1][:3] == ["git", "clone", "--filter=blob:none"]
    assert commands[-1][1:] == ["-m", "pip", "install", "-e", str(tmp_path / init.CORE_FOLDER)]
    assert (tmp_path / ".gitignore").read_text() == "output/\n*.egg-info/\n"


def test_with_core_clones_the_release_tag_of_the_installed_version(tmp_path, monkeypatch):
    commands = []
    monkeypatch.setattr(subprocess, "run", _recorder(commands))
    monkeypatch.setattr(init, "version", lambda package: "0.1.0")
    init.main([str(tmp_path), "--with-core"])

    assert commands[0][-1] == "refs/tags/v0.1.0"
    assert commands[1][:5] == ["git", "clone", "--filter=blob:none", "--branch", "v0.1.0"]


def test_with_core_clones_main_when_the_version_has_no_tag(tmp_path, monkeypatch, capsys):
    commands = []
    monkeypatch.setattr(subprocess, "run", _recorder(commands, tag_exists=False))
    init.main([str(tmp_path), "--with-core"])

    assert commands[1][:4] == ["git", "clone", "--filter=blob:none", init.CORE_URL]
    assert "no release tag" in capsys.readouterr().out


def _fake_clone(monkeypatch):
    """Make `git clone` create a small core with one example of each kind."""

    def run(command, check, **kwargs):
        if command[:2] == ["git", "ls-remote"]:
            return SimpleNamespace(stdout="")
        if command[:2] != ["git", "clone"]:
            return SimpleNamespace(stdout="v0.1.0-4-gabc1234\n")
        core = Path(command[-1])
        (core / ".git").mkdir(parents=True)
        (core / "microcircuit_lab").mkdir()
        (core / "microcircuit_lab" / "__init__.py").write_text("core code")
        for name in init.BACKENDS:
            (core / "microcircuit_lab" / "backends" / name).mkdir(parents=True)
        (core / "pyproject.toml").write_text("[project]")
        (core / "docs").mkdir()
        (core / "docs" / "config_files.md").write_text("fields")
        (core / "tests").mkdir()
        (core / "builders" / "demo").mkdir(parents=True)
        (core / "builders" / "__init__.py").write_text("")
        (core / "builders" / "demo" / "__init__.py").write_text("def main(argv=None): pass\n")
        (core / "builders" / "demo" / "__pycache__").mkdir()
        (core / "configs" / "network" / "demo").mkdir(parents=True)
        (core / "configs" / "network" / "demo" / "network.yaml").write_text("core")
        (core / "configs" / "simulation").mkdir()
        (core / "configs" / "simulation" / "demo.yaml").write_text("core")
        (core / "configs" / "analysis").mkdir()
        (core / "configs" / "analysis" / "demo.yaml").write_text("core")

    monkeypatch.setattr(subprocess, "run", run)


def test_with_core_copies_the_core_without_its_git_history(tmp_path, monkeypatch):
    _fake_clone(monkeypatch)
    init.main([str(tmp_path), "--with-core"])

    core = tmp_path / init.CORE_FOLDER
    assert (core / "microcircuit_lab" / "__init__.py").read_text() == "core code"
    assert (core / "pyproject.toml").is_file()
    assert sorted(p.name for p in core.iterdir()) == [
        ".git_archival.txt", "docs", "microcircuit_lab", "pyproject.toml"
    ]
    # the commit copied, where setuptools-scm reads the version without .git
    assert "describe-name: v0.1.0-4-gabc1234" in (core / ".git_archival.txt").read_text()


def test_with_core_keeps_an_existing_copy(tmp_path, monkeypatch, capsys):
    _fake_clone(monkeypatch)
    init.main([str(tmp_path), "--with-core"])
    (tmp_path / init.CORE_FOLDER / "microcircuit_lab" / "__init__.py").write_text("my edit")
    init.main([str(tmp_path), "--with-core"])

    assert (tmp_path / init.CORE_FOLDER / "microcircuit_lab" / "__init__.py").read_text() == "my edit"
    assert "already exists, left as it is" in capsys.readouterr().out


def test_with_core_copies_the_examples(tmp_path, monkeypatch):
    _fake_clone(monkeypatch)
    init.main([str(tmp_path), "--with-core"])

    assert (tmp_path / "builders" / "demo" / "__init__.py").is_file()
    assert not (tmp_path / "builders" / "__init__.py").exists()
    assert not (tmp_path / "builders" / "demo" / "__pycache__").exists()
    assert (tmp_path / "configs" / "network" / "demo" / "network.yaml").read_text() == "core"
    assert (tmp_path / "configs" / "simulation" / "demo.yaml").is_file()
    assert (tmp_path / "configs" / "analysis" / "demo.yaml").is_file()


def test_with_core_skips_examples_the_project_already_has(tmp_path, monkeypatch, capsys):
    _fake_clone(monkeypatch)
    (tmp_path / "configs" / "network" / "demo").mkdir(parents=True)
    (tmp_path / "configs" / "network" / "demo" / "mine.yaml").write_text("keep")
    init.main([str(tmp_path), "--with-core"])

    assert sorted(p.name for p in (tmp_path / "configs" / "network" / "demo").iterdir()) == ["mine.yaml"]
    assert "Skipped configs/network/demo (already exists)" in capsys.readouterr().out
    assert (tmp_path / "configs" / "simulation" / "demo.yaml").is_file()


def test_with_core_twice_changes_nothing(tmp_path, monkeypatch, capsys):
    _fake_clone(monkeypatch)
    init.main([str(tmp_path), "--with-core"])
    (tmp_path / "configs" / "simulation" / "demo.yaml").write_text("edited")
    capsys.readouterr()
    init.main([str(tmp_path), "--with-core"])

    assert (tmp_path / "configs" / "simulation" / "demo.yaml").read_text() == "edited"
    assert "Copied" not in capsys.readouterr().out


def _fake_source(tmp_path):
    """A core with both backends and, as the real one, example models for brian2 only."""
    source = tmp_path / "source"
    for name in ("nest", "brian2"):
        (source / "microcircuit_lab" / "backends" / name).mkdir(parents=True)
        (source / "microcircuit_lab" / "backends" / name / "simulator.py").write_text(name)
    (source / "extensions" / "brian2").mkdir(parents=True)
    (source / "extensions" / "brian2" / "model.py").write_text("brian2")
    return source


def test_core_and_examples_copy_only_the_chosen_backends(tmp_path, monkeypatch):
    source = _fake_source(tmp_path)
    monkeypatch.setattr(init, "_git", lambda *arguments: "x")
    init._copy_core(source, tmp_path / "core", ["nest"])
    init._copy_examples(source, tmp_path / "project", ["nest"])

    backends = tmp_path / "core" / "microcircuit_lab" / "backends"
    assert sorted(p.name for p in backends.iterdir()) == ["nest"]
    assert not (tmp_path / "project" / "extensions").exists()

    init._copy_examples(source, tmp_path / "project", ["brian2"])
    assert (tmp_path / "project" / "extensions" / "brian2" / "model.py").is_file()


def test_adding_a_backend_to_an_existing_copy_changes_nothing_else(tmp_path, monkeypatch):
    source = _fake_source(tmp_path)
    monkeypatch.setattr(init, "_git", lambda *arguments: "x")
    init._copy_core(source, tmp_path / "core", ["nest"])
    nest_file = tmp_path / "core" / "microcircuit_lab" / "backends" / "nest" / "simulator.py"
    nest_file.write_text("my edit")
    init._add_backends(source, tmp_path / "core", ["nest", "brian2"])

    backends = tmp_path / "core" / "microcircuit_lab" / "backends"
    assert (backends / "brian2" / "simulator.py").read_text() == "brian2"
    assert nest_file.read_text() == "my edit"
