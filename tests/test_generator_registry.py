"""Automatic discovery of model generators."""

import pytest

from microcircuit_lab.generators import discover_generators


def test_discovery_finds_at_least_one_model() -> None:
    # Not asserting on specific names: humam/pd14 are reference examples,
    # not a fixed set -- a fork may remove or replace them.
    assert discover_generators()


def test_every_discovered_generator_is_its_main_function() -> None:
    for name, main in discover_generators().items():
        assert callable(main), f"generators.{name} has no callable main()"


def test_generator_main_takes_an_argv_list() -> None:
    # The one hook scripts/generate.py relies on: main(argv). --help must
    # build the parser and exit cleanly without running generation.
    for name, main in discover_generators().items():
        with pytest.raises(SystemExit) as exit_info:
            main(["--help"])
        assert exit_info.value.code == 0, f"{name}.main(['--help']) exited non-zero"
