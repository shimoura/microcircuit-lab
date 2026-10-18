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
