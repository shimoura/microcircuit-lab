"""The `microcircuit-lab` command forwards to the right subcommand."""

import pytest

from microcircuit_lab import cli


def test_command_forwards_remaining_arguments(monkeypatch):
    received = []
    monkeypatch.setitem(cli.COMMANDS, "generate", received.append)
    cli.main(["generate", "my_model", "--help"])
    assert received == [["my_model", "--help"]]


def test_unknown_command_lists_the_available_ones():
    with pytest.raises(SystemExit, match="generate, run, new-builder"):
        cli.main(["nope"])


def test_no_arguments_prints_usage(capsys):
    cli.main([])
    assert "microcircuit-lab generate" in capsys.readouterr().out


def test_version_prints_the_installed_version(capsys):
    from importlib.metadata import version

    cli.main(["--version"])
    assert version("microcircuit_lab") in capsys.readouterr().out


def test_missing_network_names_the_folder_and_the_networks_next_to_it(tmp_path):
    from microcircuit_lab.network.load import read_network_files

    (tmp_path / "toy").mkdir()
    (tmp_path / "toy" / "network.yaml").write_text("{}")
    with pytest.raises(FileNotFoundError) as error:
        read_network_files(tmp_path / "toyy")
    assert f"No network at {tmp_path / 'toyy'} (no network.yaml)." in str(error.value)
    assert f"Networks in {tmp_path}: toy" in str(error.value)
