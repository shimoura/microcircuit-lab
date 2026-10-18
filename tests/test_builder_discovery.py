"""Automatic discovery of model builders. Uses throwaway builders written to
a temporary folder, so the tests do not depend on which models are bundled."""

from importlib.metadata import EntryPoint
from pathlib import Path

import pytest

from microcircuit_lab.io import builders as builders_module
from microcircuit_lab.io import discover_builders

BUILDER = """\
import argparse


def main(argv=None):
    argparse.ArgumentParser(prog="demo").parse_args(argv)
    return "ran"
"""


def _write_builder(folder: Path, name: str, source: str) -> None:
    (folder / name).mkdir(parents=True)
    (folder / name / "__init__.py").write_text(source)


def test_every_bundled_builder_answers_help() -> None:
    # Does not name any builder and passes with none: whichever builders/
    # contains must still import and build its argument parser.
    for name, main in discover_builders().items():
        with pytest.raises(SystemExit) as exit_info:
            main(["--help"])
        assert exit_info.value.code == 0, f"{name}.main(['--help']) exited non-zero"


def test_a_missing_builders_folder_gives_no_builders(tmp_path: Path) -> None:
    assert discover_builders(tmp_path / "no_such_folder") == {}


def test_a_folder_with_a_main_is_found_and_one_without_is_skipped(tmp_path: Path) -> None:
    folder = tmp_path / "my_builders"
    _write_builder(folder, "with_main", BUILDER)
    _write_builder(folder, "without_main", "")

    found = discover_builders(folder)

    assert list(found) == ["with_main"]
    assert found["with_main"]([]) == "ran"


def test_builder_main_takes_an_argv_list(tmp_path: Path) -> None:
    # The one hook scripts/generate.py relies on: main(argv). --help must
    # build the parser and exit cleanly without running generation.
    folder = tmp_path / "other_builders"
    _write_builder(folder, "demo", BUILDER)

    with pytest.raises(SystemExit) as exit_info:
        discover_builders(folder)["demo"](["--help"])

    assert exit_info.value.code == 0


def test_a_builder_that_fails_to_import_raises(tmp_path: Path) -> None:
    folder = tmp_path / "broken_builders"
    _write_builder(folder, "broken", "raise RuntimeError('broken builder')\n")

    with pytest.raises(RuntimeError, match="broken builder"):
        discover_builders(folder)


def test_an_installed_package_can_register_a_builder(monkeypatch, tmp_path: Path) -> None:
    external = EntryPoint(
        name="external_model", value="builtins:print", group=builders_module.BUILDER_ENTRY_POINT_GROUP
    )
    monkeypatch.setattr(builders_module, "entry_points", lambda group: [external])

    found = discover_builders(tmp_path / "no_such_folder")

    assert found == {"external_model": print}
