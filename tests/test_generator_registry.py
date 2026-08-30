"""Automatic discovery of model generators."""

from types import ModuleType

import pytest

from microcircuit_lab.generators import GENERATORS, discover_generators


def test_discovery_finds_at_least_one_model() -> None:
    # Not asserting on specific names: humam/pd14 are reference examples,
    # not a fixed set -- a fork may remove or replace them.
    assert GENERATORS


def test_every_discovered_generator_is_a_package_exposing_main() -> None:
    for name, module in GENERATORS.items():
        assert isinstance(module, ModuleType)
        assert callable(getattr(module, "main", None)), f"generators.{name} has no main()"


def test_discovery_needs_no_hardcoded_list() -> None:
    # discover_generators() rescans the package directory on each call;
    # dropping a package in is all it takes to register a model.
    assert set(discover_generators()) == set(GENERATORS)


def test_generator_main_takes_an_argv_list() -> None:
    # The one hook scripts/generate.py relies on: main(argv). --help must
    # build the parser and exit cleanly without running generation.
    for name, module in GENERATORS.items():
        with pytest.raises(SystemExit) as exit_info:
            module.main(["--help"])
        assert exit_info.value.code == 0, f"{name}.main(['--help']) exited non-zero"
