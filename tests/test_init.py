"""`microcircuit-lab init`: project folders, never overwriting, --with-core and its examples."""

import subprocess
from pathlib import Path

from microcircuit_lab.cli import init


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


def test_with_core_clones_installs_and_ignores_the_folder(tmp_path, monkeypatch):
    commands = []
    monkeypatch.setattr(subprocess, "run", lambda command, check: commands.append(command))
    (tmp_path / ".gitignore").write_text("output/\n")
    init.main([str(tmp_path), "--with-core"])
    init.main([str(tmp_path), "--with-core"])

    assert commands[0][:2] == ["git", "clone"]
    assert commands[1][1:5] == ["-m", "pip", "install", "-e"]
    assert (tmp_path / ".gitignore").read_text() == "output/\nmicrocircuit-lab/\n"


def _fake_clone(monkeypatch):
    """Make `git clone` create a small core with one example of each kind."""

    def run(command, check):
        if command[:2] != ["git", "clone"]:
            return
        core = Path(command[-1])
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
