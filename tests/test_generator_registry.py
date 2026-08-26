"""Tests for automatic discovery of model generators."""

import argparse

from microcircuit_lab.generators import GENERATOR_REGISTRY


def test_known_models_are_discovered() -> None:
    assert set(GENERATOR_REGISTRY) >= {"humam", "pd14"}


def test_every_registered_generator_wires_up_a_subparser() -> None:
    for name, add_cli in GENERATOR_REGISTRY.items():
        assert callable(add_cli)

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="model")
        subparser = subparsers.add_parser(name)

        add_cli(subparser)
