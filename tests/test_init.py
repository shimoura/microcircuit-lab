"""`microcircuit-lab init`: project folders, never overwriting, and --with-core."""

import subprocess

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
