"""`microcircuit-lab init`: project folders, the toy example, --example, never overwriting, and --with-core (a copy of the core)."""

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from microcircuit_lab.cli import init


def _recorder(commands, tag_exists=True):
    """A stand-in for subprocess.run that records each command; `git ls-remote`
    answers as if the release tag exists (or not)."""

    def run(command, check, **kwargs):
        commands.append(command)
        return SimpleNamespace(stdout="abc123\trefs/tags/v0.1.0\n" if tag_exists else "")

    return run


def test_creates_the_project_folders(tmp_path, monkeypatch):
    _fake_clone(monkeypatch)
    init.main([str(tmp_path / "proj")])
    for name in ("builders", "analyses", "configs", "experiments"):
        assert (tmp_path / "proj" / name).is_dir()


def test_existing_files_are_left_alone(tmp_path, monkeypatch, capsys):
    _fake_clone(monkeypatch)
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
    assert commands[1][:4] == ["git", "clone", "--quiet", "--filter=blob:none"]
    assert commands[-1][1:] == ["-m", "pip", "install", "-e", str(tmp_path / init.CORE_FOLDER)]
    assert (tmp_path / ".gitignore").read_text() == "output/\n*.egg-info/\n"


def test_with_core_clones_the_release_tag_of_the_installed_version(tmp_path, monkeypatch):
    commands = []
    monkeypatch.setattr(subprocess, "run", _recorder(commands))
    monkeypatch.setattr(init, "version", lambda package: "0.1.0")
    init.main([str(tmp_path), "--with-core"])

    assert commands[0][-1] == "refs/tags/v0.1.0"
    assert commands[1][:6] == ["git", "clone", "--quiet", "--filter=blob:none", "--branch", "v0.1.0"]


def test_with_core_clones_main_when_the_version_has_no_tag(tmp_path, monkeypatch, capsys):
    commands = []
    monkeypatch.setattr(subprocess, "run", _recorder(commands, tag_exists=False))
    init.main([str(tmp_path), "--with-core"])

    assert commands[1][:5] == ["git", "clone", "--quiet", "--filter=blob:none", init.CORE_URL]
    assert "no release tag" in capsys.readouterr().out


def _fake_clone(monkeypatch):
    """Make `git clone` create a small core with the toy example and a demo
    example that has one item of each kind."""

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
        toy, demo = core / "examples" / "toy", core / "examples" / "demo"
        for path in init.TOY_EXAMPLE:
            (toy / path).parent.mkdir(parents=True, exist_ok=True)
            (toy / path).write_text("toy")
        (demo / "builders" / "demo" / "__pycache__").mkdir(parents=True)
        (demo / "builders" / "__init__.py").write_text("")
        (demo / "builders" / "demo" / "__init__.py").write_text("def main(argv=None): pass\n")
        (demo / "analyses").mkdir()
        (demo / "analyses" / "demo_raster.py").write_text("demo")
        for folder in ("network", "simulation", "analysis"):
            (demo / "configs" / folder).mkdir(parents=True)
        (demo / "configs" / "network" / "demo").mkdir()
        (demo / "configs" / "network" / "demo" / "network.yaml").write_text("demo")
        (demo / "configs" / "simulation" / "demo.yaml").write_text("demo")
        (demo / "configs" / "analysis" / "demo.yaml").write_text("demo")
        # The same model file in both examples, as the real ones share them.
        for example in (toy, demo):
            (example / "extensions" / "brian2").mkdir(parents=True)
            (example / "extensions" / "brian2" / "__init__.py").write_text("")
            (example / "extensions" / "brian2" / "model.py").write_text("brian2")

    monkeypatch.setattr(subprocess, "run", run)


def test_copies_only_the_toy_example_and_the_brian2_models_with_brian2(tmp_path, monkeypatch):
    _fake_clone(monkeypatch)
    monkeypatch.setattr(init.importlib.util, "find_spec", lambda name: object() if name == "nest" else None)
    init.main([str(tmp_path / "without")])
    monkeypatch.setattr(init.importlib.util, "find_spec", lambda name: object())
    init.main([str(tmp_path / "with")])

    for path in init.TOY_EXAMPLE:
        assert (tmp_path / "without" / path).read_text() == "toy"
    assert not (tmp_path / "without" / "builders" / "demo").exists()
    assert not (tmp_path / "without" / "extensions" / "brian2").exists()
    assert (tmp_path / "with" / "extensions" / "brian2" / "model.py").is_file()
    assert not (tmp_path / "with" / "extensions" / "brian2" / "__init__.py").exists()


def test_without_a_connection_the_folders_are_still_made(tmp_path, monkeypatch, capsys):
    def offline(command, check, **kwargs):
        raise subprocess.CalledProcessError(128, command)

    monkeypatch.setattr(subprocess, "run", offline)
    init.main([str(tmp_path)])

    assert (tmp_path / "builders").is_dir()
    assert "Nothing was copied from the core repository" in capsys.readouterr().out


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


def test_with_core_copies_the_core_and_no_other_example(tmp_path, monkeypatch):
    _fake_clone(monkeypatch)
    init.main([str(tmp_path), "--with-core"])

    assert (tmp_path / "builders" / "toy").exists()
    assert not (tmp_path / "builders" / "demo").exists()


def test_an_example_is_merged_into_the_project_folders(tmp_path, monkeypatch, capsys):
    _fake_clone(monkeypatch)
    init.main([str(tmp_path), "--example", "demo"])

    assert (tmp_path / "builders" / "demo" / "__init__.py").is_file()
    assert not (tmp_path / "builders" / "__init__.py").exists()
    assert not (tmp_path / "builders" / "demo" / "__pycache__").exists()
    assert (tmp_path / "analyses" / "demo_raster.py").is_file()
    assert (tmp_path / "configs" / "network" / "demo" / "network.yaml").read_text() == "demo"
    assert (tmp_path / "configs" / "simulation" / "demo.yaml").is_file()
    assert (tmp_path / "configs" / "analysis" / "demo.yaml").is_file()
    # The model file the toy already brought is the same: copied once, no message.
    assert "extensions/brian2/model.py" not in capsys.readouterr().out.split("Copied builders/demo")[1]


def test_an_unknown_example_lists_the_examples(tmp_path, monkeypatch):
    _fake_clone(monkeypatch)
    with pytest.raises(SystemExit, match="No example named nope; the examples are: demo, toy"):
        init.main([str(tmp_path), "--example", "nope"])


def test_an_example_that_clashes_with_the_project_is_not_copied(tmp_path, monkeypatch, capsys):
    _fake_clone(monkeypatch)
    (tmp_path / "configs" / "network" / "demo").mkdir(parents=True)
    (tmp_path / "configs" / "network" / "demo" / "mine.yaml").write_text("keep")
    init.main([str(tmp_path), "--example", "demo"])

    assert sorted(p.name for p in (tmp_path / "configs" / "network" / "demo").iterdir()) == ["mine.yaml"]
    assert not (tmp_path / "builders" / "demo").exists()
    assert "Not copied: the demo example, because the project has a different configs/network/demo" in capsys.readouterr().out


def test_init_twice_says_nothing_and_keeps_a_changed_toy(tmp_path, monkeypatch, capsys):
    _fake_clone(monkeypatch)
    init.main([str(tmp_path), "--example", "demo", "--with-core"])
    (tmp_path / "configs" / "simulation" / "toy.yaml").write_text("edited")
    capsys.readouterr()
    init.main([str(tmp_path), "--example", "demo", "--with-core"])

    assert (tmp_path / "configs" / "simulation" / "toy.yaml").read_text() == "edited"
    out = capsys.readouterr().out
    assert "Copied" not in out and "Not copied" not in out


def _fake_source(tmp_path):
    """A core with both backends and, as the real one, example models for brian2 only."""
    source = tmp_path / "source"
    for name in ("nest", "brian2"):
        (source / "microcircuit_lab" / "backends" / name).mkdir(parents=True)
        (source / "microcircuit_lab" / "backends" / name / "simulator.py").write_text(name)
    (source / "examples" / "demo" / "extensions" / "brian2").mkdir(parents=True)
    (source / "examples" / "demo" / "extensions" / "brian2" / "model.py").write_text("brian2")
    return source


def test_core_and_examples_copy_only_the_chosen_backends(tmp_path, monkeypatch):
    source = _fake_source(tmp_path)
    monkeypatch.setattr(init, "_git", lambda *arguments: "x")
    init._copy_core(source, tmp_path / "core", ["nest"])
    demo = source / "examples" / "demo"

    backends = tmp_path / "core" / "microcircuit_lab" / "backends"
    assert sorted(p.name for p in backends.iterdir()) == ["nest"]
    assert init._example_items(demo, ["nest"]) == []
    assert init._example_items(demo, ["brian2"]) == ["extensions/brian2/model.py"]


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
